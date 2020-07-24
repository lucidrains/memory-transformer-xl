## Memory Transformer-XL

A combination of Transformer-XL with ideas from Memory Transformers. While in Transformer-XL the memory is just a FIFO queue, this repository will attempt to update the memory (queries) against the incoming hidden states (keys / values) with a memory attention network. The memory attention network will utilize linear attention to be performant, followed by GRU gating, and will be backpropagated through time to learn how to properly store and discard new/old memory.

## Install

```bash
$ pip install memory-transformer-xl
```

## Usage

```python
import torch
from memory_transformer_xl import MemoryTransformerXL

model = MemoryTransformerXL(
    num_tokens = 20000,
    dim = 1024,
    heads = 8,
    depth = 8,
    seq_len = 512,
    mem_len = 256,            # short term memory (the memory from transformer-xl)
    lmem_len = 256,           # long term memory (memory attention network attending to short term memory and hidden activations)
    memory_layers = [6,7,8]   # which layers to use memory, only the later layers are actually needed
).cuda()

x1 = torch.randint(0, 20000, (1, 512)).cuda()
logits1, mem1 = model(x1)

x2 = torch.randint(0, 20000, (1, 512)).cuda()
logits2, mem2 = model(x2, memories = mem1)

# and so on with carrying over memories...
```

## Citations

```bibtex
@article{Dai_2019,
   title  = {Transformer-XL: Attentive Language Models beyond a Fixed-Length Context},
   url    = {http://dx.doi.org/10.18653/v1/P19-1285},
   DOI    = {10.18653/v1/p19-1285},
   journal={Proceedings of the 57th Annual Meeting of the Association for Computational Linguistics},
   publisher = {Association for Computational Linguistics},
   author = {Dai, Zihang and Yang, Zhilin and Yang, Yiming and Carbonell, Jaime and Le, Quoc and Salakhutdinov, Ruslan},
   year = {2019}
}
```

```bibtex
@misc{burtsev2020memory,
    title   = {Memory Transformer},
    author  = {Mikhail S. Burtsev and Grigory V. Sapunov},
    year    = {2020},
    eprint  = {2006.11527},
    archivePrefix = {arXiv},
    primaryClass = {cs.CL}
}
```

```bibtex
@misc{parisotto2019stabilizing,
    title     = {Stabilizing Transformers for Reinforcement Learning},
    author    = {Emilio Parisotto and H. Francis Song and Jack W. Rae and Razvan Pascanu and Caglar Gulcehre and Siddhant M. Jayakumar and Max Jaderberg and Raphael Lopez Kaufman and Aidan Clark and Seb Noury and Matthew M. Botvinick and Nicolas Heess and Raia Hadsell},
    year      = {2019},
    eprint    = {1910.06764},
    archivePrefix = {arXiv},
    primaryClass = {cs.LG}
}
```

```bibtex
@article{shen2019efficient,
  author    = {Zhuoran Shen and Mingyuan Zhang and Haiyu Zhao and Shuai Yi and Hongsheng Li},
  title     = {Efficient Attention: Attention with Linear Complexities},
  journal   = {CoRR},
  volume    = {abs/1812.01243},
  year      = {2018},
  url       = {http://arxiv.org/abs/1812.01243}
}
```

```bibtex
@article{DBLP:journals/corr/abs-1907-01470,
    author    = {Sainbayar Sukhbaatar and
               Edouard Grave and
               Guillaume Lample and
               Herv{\'{e}} J{\'{e}}gou and
               Armand Joulin},
    title     = {Augmenting Self-attention with Persistent Memory},
    journal   = {CoRR},
    volume    = {abs/1907.01470},
    year      = {2019},
    url       = {http://arxiv.org/abs/1907.01470}
}
```

```bibtex
@misc{vecoven2020bioinspired,
    title   = {A bio-inspired bistable recurrent cell allows for long-lasting memory},
    author  = {Nicolas Vecoven and Damien Ernst and Guillaume Drion},
    year    = {2020},
    eprint  = {2006.05252},
    archivePrefix = {arXiv},
    primaryClass = {cs.NE}
}
```

*<a href="https://youtu.be/AIiwuClvH6k?t=48">Memory is attention through time</a>* - Alex Graves
