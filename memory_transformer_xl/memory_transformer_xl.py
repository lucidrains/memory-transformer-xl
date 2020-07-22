import torch
from torch import nn
import torch.nn.functional as F

from mogrifier import Mogrifier

from collections import namedtuple
from functools import partial
from inspect import isfunction

# structs

Memory = namedtuple('Memory', ['short', 'long'])

# helper functions

def to(t):
    return {'dtype': t.dtype, 'device': t.device}

def cast_tuple(el):
    return el if isinstance(el, tuple) else (el,)

def default(x, val):
    if x is not None:
        return x
    return val if not isfunction(val) else val()

def max_neg_value(tensor):
    return -torch.finfo(tensor.dtype).max

def reshape_dim(t, dim, split_dims):
    shape = list(t.shape)
    num_dims = len(shape)
    dim = (dim + num_dims) % num_dims
    shape[dim:dim+1] = split_dims
    return t.reshape(shape)

def split_at_index(dim, index, t):
    pre_slices = (slice(None),) * dim
    l = (*pre_slices, slice(None, index))
    r = (*pre_slices, slice(index, None))
    return t[l], t[r]

def shift(x):
    *_, i, j = x.shape
    zero_pad = torch.zeros((*_, i, i), **to(x))
    x = torch.cat([x, zero_pad], -1)
    l = i + j - 1
    x = x.view(*_, -1)
    zero_pad = torch.zeros(*_, -x.size(-1) % l, **to(x))
    shifted = torch.cat([x, zero_pad], -1).view(*_, -1, l)
    return shifted[..., :i, i - 1:]

def iterate_tensor(t):
    length = t.shape[0]
    for ind in range(length):
        yield t[ind]

# helper classes

class Residual(nn.Module):
    def __init__(self, fn):
        super().__init__()
        self.fn = fn
    def forward(self, x, **kwargs):
        return self.fn(x, **kwargs) + x

class GRUGating(nn.Module):
    def __init__(self, dim, fn, mogrify = False):
        super().__init__()
        self.dim = dim
        self.fn = fn
        self.gru = nn.GRU(dim, dim)
        self.mogrify = Mogrifier(dim, factorize_k = dim // 4) if mogrify else None

    def forward(self, x, **kwargs):
        shape = x.shape
        dim = self.dim

        y = self.fn(x, **kwargs)

        if self.mogrify is not None:
            y, x = self.mogrify(y, x)

        gated_output, _ = self.gru(
            y.reshape(1, -1, dim),
            x.reshape(1, -1, dim)
        )

        return gated_output.reshape(shape)

class PreNorm(nn.Module):
    def __init__(self, dim, fn):
        super().__init__()
        self.norm = nn.LayerNorm(dim)
        self.fn = fn
    def forward(self, x, **kwargs):
        x = self.norm(x)
        return self.fn(x, **kwargs)

# feedforward

class GELU_(nn.Module):
    def forward(self, x):
        return 0.5 * x * (1 + torch.tanh(math.sqrt(2 / math.pi) * (x + 0.044715 * torch.pow(x, 3))))

GELU = nn.GELU if hasattr(nn, 'GELU') else GELU_

class FeedForward(nn.Module):
    def __init__(self, dim, mult = 4, dropout = 0., activation = None, glu = False):
        super().__init__()
        activation = default(activation, GELU)

        self.glu = glu
        self.w1 = nn.Linear(dim, dim * mult * (2 if glu else 1))
        self.act = activation()
        self.dropout = nn.Dropout(dropout)
        self.w2 = nn.Linear(dim * mult, dim)

    def forward(self, x, **kwargs):
        if not self.glu:
            x = self.w1(x)
            x = self.act(x)
        else:
            x, v = self.w1(x).chunk(2, dim=-1)
            x = self.act(x) * v

        x = self.dropout(x)
        x = self.w2(x)
        return x

# attention.

class SelfAttention(nn.Module):
    def __init__(self, dim, seq_len, mem_len, lmem_len, heads = 8, attn_dropout = 0., dropout = 0., memory_attn_dropout = 0., one_kv_head = False):
        super().__init__()
        assert (dim % heads) == 0, 'dimension must be divisible by the number of heads'

        self.heads = heads
        self.dim_head = dim // heads
        self.seq_len = seq_len
        self.mem_len = mem_len
        self.lmem_len = lmem_len
        self.scale = self.dim_head ** (-0.5)

        self.to_q = nn.Linear(dim, dim, bias = False)

        kv_dim = self.dim_head if one_kv_head else dim
        self.to_kv = nn.Linear(dim, kv_dim * 2, bias = False)
        self.to_out = nn.Linear(dim, dim)

        self.attn_dropout = nn.Dropout(attn_dropout)
        self.dropout = nn.Dropout(dropout)

        self.memory_attn_dropout = nn.Dropout(memory_attn_dropout)

    def forward(self, x, memories = None, pos_emb = None, input_mask = None, calc_memory = True, **kwargs):
        b, t, e, h, dim_h = *x.shape, self.heads, self.dim_head

        memories = default(memories, (None, None))
        mem, lmem = memories

        init_mem = lambda: torch.empty(b, 0, e, **to(x))
        mem = default(mem, init_mem)
        lmem = default(lmem, init_mem)

        mem_len = mem.shape[1]
        lmem_len = lmem.shape[1]

        q = self.to_q(x)

        kv_input = torch.cat((lmem, mem, x), dim=1)
        kv_len = kv_input.shape[1]
        k, v = self.to_kv(kv_input).chunk(2, dim=-1)

        merge_heads = lambda x: reshape_dim(x, -1, (-1, dim_h)).transpose(1, 2)
        q, k, v = map(merge_heads, (q, k, v))

        k, v = map(lambda x: x.expand(-1, h, -1, -1), (k, v))

        dots = torch.einsum('bhid,bhjd->bhij', q, k) * self.scale
        mask_value = max_neg_value(dots)

        if pos_emb is not None:
            pos_emb = pos_emb[:, -kv_len:].type(q.dtype)
            pos_dots = torch.einsum('bhid,hjd->bhij', q, pos_emb) * self.scale
            pos_dots = shift(pos_dots)
            dots = dots + pos_dots

        if input_mask is not None:
            mask = input_mask[:, None, :, None] * input_mask[:, None, None, :]
            mask = F.pad(mask, (mem_len + lmem_len, 0), value = True)
            dots.masked_fill_(~mask, mask_value)

        total_mem_len = mem_len + lmem_len
        mask = torch.ones(t, t + total_mem_len, **to(x)).triu_(diagonal = 1 + total_mem_len).bool()
        dots.masked_fill_(mask[None, None, ...], mask_value)

        attn = dots.softmax(dim=-1)
        attn = self.attn_dropout(attn)

        out = torch.einsum('bhij,bhjd->bhid', attn, v)
        out = out.transpose(1, 2).reshape(b, t, -1)
        out = self.to_out(out)

        return self.dropout(out)

# memory attention network

class MemoryAttentionNetwork(nn.Module):
    def __init__(self, dim, num_memory_depth, mem_len, lmem_len, heads = 8):
        super().__init__()
        self.num_memory_depth = num_memory_depth
        self.mem_len = mem_len
        self.lmem_len = lmem_len

        dim_head = dim // heads
        self.dim_head = dim_head

        self.init_lmem = nn.Parameter(torch.zeros(1, 1, lmem_len, dim))

        self.norm = nn.LayerNorm(dim, elementwise_affine = False)

        self.to_q = nn.Parameter(torch.randn(dim, dim))
        self.to_kv = nn.Parameter(torch.randn(dim, 2 * dim))
        self.to_out = nn.Parameter(torch.randn(dim, dim))

        self.rezero_g = nn.Parameter(torch.tensor(0.))

    def forward(self, lmem, smem, hiddens):
        hiddens = hiddens.detach()
        batch, dim_head, mem_depth = lmem.shape[1], self.dim_head, self.num_memory_depth

        if lmem.shape[2] == 0:
            lmem = self.init_lmem.expand(mem_depth, batch, -1, -1)

        # clone weights to avoid inplace error

        w_q, w_kv, w_out, rezero_g = map(torch.clone, (self.to_q, self.to_kv, self.to_out, self.rezero_g))

        # use efficient linear attention for updating long term memory

        normed_lmem = self.norm(lmem)
        q = torch.einsum('mbnd,de->mbne', normed_lmem, w_q)

        kv_input = torch.cat((normed_lmem, smem, hiddens), dim=2)
        k, v = torch.einsum('mbnd,de->mbne', kv_input, w_kv).chunk(2, dim=-1)

        q, k, v = map(lambda t: reshape_dim(t, -1, (-1, dim_head)).transpose(2, 3), (q, k, v))
        q, k = map(lambda t: t * dim_head ** -0.25, (q, k))

        q = q.softmax(dim=-1)
        k = k.softmax(dim=-2)

        context = torch.einsum('mbhnd,mbhne->mbhde', k, v)
        out = torch.einsum('mbhnd,mbhde->mbhne', q, context)

        out = out.transpose(2, 3).reshape_as(lmem)
        next_lmem = torch.einsum('mbnd,de->mbne', out, w_out)

        # update the memory with rezero gating for now
        # will update to use mogrifier

        next_lmem = next_lmem * rezero_g + lmem

        # fifo queue the short term memory
        _, next_mem = split_at_index(2, -self.mem_len, torch.cat((smem, hiddens), dim=2))
        next_mem = next_mem.detach()

        return Memory(short = next_mem, long = next_lmem)

# transformer

class MemoryTransformerXL(nn.Module):
    def __init__(self, num_tokens, dim, seq_len, depth, emb_dim = None, memory_layers = None, mem_len = None, lmem_len = None, heads = 8, gru_gated_residual = False, mogrify_gru = False, attn_dropout = 0., ff_glu = False, ff_dropout = 0., attn_layer_dropout = 0., one_kv_head = False):
        super().__init__()
        emb_dim = default(emb_dim, dim)
        mem_len = default(mem_len, seq_len)
        lmem_len = default(lmem_len, mem_len)

        memory_layers = default(memory_layers, list(range(1, depth + 1)))

        assert mem_len >= seq_len, 'length of short-term memory should be at least the sequence length'
        assert all([layer > 0 and layer <= depth for layer in memory_layers]), 'one of the indicated memory layers is invalid'

        self.mem_len = mem_len
        self.seq_len = seq_len

        self.depth = depth
        self.memory_layers = list(memory_layers)

        self.token_emb = nn.Embedding(num_tokens, emb_dim)
        self.to_model_dim = nn.Identity() if emb_dim == dim else nn.Linear(emb_dim, dim)

        seq_and_mem_len = seq_len + mem_len + lmem_len
        self.pos_emb = nn.Parameter(torch.zeros(heads, seq_and_mem_len, dim // heads))
        
        self.to_logits = nn.Sequential(
            nn.Identity() if emb_dim == dim else nn.Linear(dim, emb_dim),
            nn.Linear(emb_dim, num_tokens)
        )

        wrapper = partial(GRUGating, dim, mogrify = mogrify_gru) if gru_gated_residual else Residual

        self.attn_layers = nn.ModuleList([wrapper(PreNorm(dim, SelfAttention(dim, seq_len, mem_len, lmem_len, heads, dropout = attn_layer_dropout, attn_dropout = attn_dropout, one_kv_head = one_kv_head))) for _ in range(depth)])
        self.ff_layers = nn.ModuleList([wrapper(PreNorm(dim, FeedForward(dim, dropout = ff_dropout, glu = ff_glu))) for _ in range(depth)])

        self.memory_network = MemoryAttentionNetwork(dim, len(self.memory_layers), mem_len, lmem_len)

    def forward(self, x, memories = None, mask = None):
        x = self.token_emb(x)
        x = self.to_model_dim(x)
        b, t, d = x.shape

        assert t <= self.seq_len, f'input contains a sequence length {t} that is greater than the designated maximum sequence length {self.seq_len}'

        memories = default(memories, (None, None))
        mem, lmem = memories

        num_memory_layers = len(self.memory_layers)
        init_mem = lambda: torch.empty(num_memory_layers, b, 0, d, **to(x))

        mem = default(mem, init_mem)
        lmem = default(lmem, init_mem)

        mem_len, lmem_len = map(lambda t: t.shape[2], (mem, lmem))
        total_len = mem_len + lmem_len + self.seq_len

        pos_emb = self.pos_emb[:, (self.seq_len - t):total_len]
        mem_iter, lmem_iter = map(iterate_tensor, (mem, lmem))

        hiddens = []

        for ind, (attn, ff) in enumerate(zip(self.attn_layers, self.ff_layers)):
            layer_num = ind + 1
            use_memory = layer_num in self.memory_layers
            memories = map(next, (mem_iter, lmem_iter)) if use_memory else None

            if use_memory:
                hiddens.append(x)

            x = attn(x, memories = memories, calc_memory = use_memory, input_mask = mask, pos_emb = pos_emb)
            x = ff(x)

        hiddens = torch.stack(hiddens)
        out = self.to_logits(x)

        # calculate next memory state

        next_memory = self.memory_network(lmem, mem, hiddens)
        return out, next_memory
