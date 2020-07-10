## Memory Transformer

A combination of Transformer-XL with ideas from Memory Transformers. While in Transformer-XL the memory is just a FIFO queue, this repository will attempt to update the memory (queries) against the incoming hidden states (keys / values) with a memory attention network. The memory attention network will utilize linear attention to be performant, and will be backpropagated through time to learn how to properly store and discard new/old memory.


## Citations

```bibtex
@article{Dai_2019,
   title={Transformer-XL: Attentive Language Models beyond a Fixed-Length Context},
   url={http://dx.doi.org/10.18653/v1/P19-1285},
   DOI={10.18653/v1/p19-1285},
   journal={Proceedings of the 57th Annual Meeting of the Association for Computational Linguistics},
   publisher={Association for Computational Linguistics},
   author={Dai, Zihang and Yang, Zhilin and Yang, Yiming and Carbonell, Jaime and Le, Quoc and Salakhutdinov, Ruslan},
   year={2019}
}
```

```bibtex
@misc{burtsev2020memory,
    title={Memory Transformer},
    author={Mikhail S. Burtsev and Grigory V. Sapunov},
    year={2020},
    eprint={2006.11527},
    archivePrefix={arXiv},
    primaryClass={cs.CL}
}
```
