from setuptools import setup, find_packages

setup(
  name = 'memory-transformer-xl',
  packages = find_packages(exclude=['examples']),
  version = '0.0.3',
  license='MIT',
  description = 'Memory Transformer-XL, a variant of Transformer-XL that uses linear attention update long term memory',
  author = 'Phil Wang',
  author_email = 'lucidrains@gmail.com',
  url = 'https://github.com/lucidrains/memory-transformer-xl',
  keywords = ['attention mechanism', 'artificial intelligence', 'transformer', 'deep learning'],
  install_requires=[
      'torch',
      'mogrifier'
  ],
  classifiers=[
      'Development Status :: 4 - Beta',
      'Intended Audience :: Developers',
      'Topic :: Scientific/Engineering :: Artificial Intelligence',
      'License :: OSI Approved :: MIT License',
      'Programming Language :: Python :: 3.6',
  ],
)