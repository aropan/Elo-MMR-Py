# Elo-MMR-Py

Python bindings for [Elo-MRR](https://github.com/EbTech/Elo-MMR).

## Installation

You can install using pip. This is the easiest way to install the package and its dependencies.

### Install from PyPI

To install the latest released version from PyPI, run the following command:

```python
pip install Elo-MMR-Py
```

This will download and install the latest version of Elo-MMR-Py from PyPI.

### Install from Source

To install Elo-MMR-Py directly from the source code using Git, run:


```python
pip install git+https://github.com/aropan/Elo-MMR-Py.git
```

#### Usage

After installation, you can import and use Elo-MMR-Py in your Python projects:

```python
from elo_mmr_py import Contest, rate

contests = [
    Contest(standings=[('player_1', 0, 0), ('player_2', 1, 1), ('player_3', 2, 2)]),
    Contest(standings=[('player_1', 0, 1), ('player_2', 0, 1), ('player_3', 2, 2)]),
    Contest(standings=[('player_1', 0, 0), ('player_2', 1, 2), ('player_3', 1, 2)]),
    Contest(standings=[('player_4', 0, 0), ('player_1', 1, 1), ('player_2', 2, 2), ('player_3', 3, 3)]),
    Contest(standings=[('player_4', 0, 0), ('player_1', 1, 1), ('player_2', 2, 2), ('player_3', 3, 3)]),
]
players = rate(contests)

from pprint import pprint
pprint(players)
```

Output for example above:

```python
{'player_1': Player(name='player_1',
                    rating=1675,
                    events=[PyPlayerEvent(contest_index=0, rating_mu=1705, rating_sig=171, perf_score=1744, place=0),
                            PyPlayerEvent(contest_index=1, rating_mu=1663, rating_sig=130, perf_score=1618, place=0),
                            PyPlayerEvent(contest_index=2, rating_mu=1686, rating_sig=111, perf_score=1728, place=0),
                            PyPlayerEvent(contest_index=3, rating_mu=1678, rating_sig=100, perf_score=1660, place=1),
                            PyPlayerEvent(contest_index=4, rating_mu=1675, rating_sig=94, perf_score=1666, place=1)]),
 'player_2': Player(name='player_2',
                    rating=1483,
                    events=[PyPlayerEvent(contest_index=0, rating_mu=1500, rating_sig=171, perf_score=1500, place=1),
                            PyPlayerEvent(contest_index=1, rating_mu=1555, rating_sig=130, perf_score=1618, place=0),
                            PyPlayerEvent(contest_index=2, rating_mu=1500, rating_sig=111, perf_score=1393, place=1),
                            PyPlayerEvent(contest_index=3, rating_mu=1487, rating_sig=100, perf_score=1459, place=2),
                            PyPlayerEvent(contest_index=4, rating_mu=1483, rating_sig=94, perf_score=1471, place=2)]),
 'player_3': Player(name='player_3',
                    rating=1279,
                    events=[PyPlayerEvent(contest_index=0, rating_mu=1295, rating_sig=171, perf_score=1256, place=2),
                            PyPlayerEvent(contest_index=1, rating_mu=1270, rating_sig=130, perf_score=1242, place=2),
                            PyPlayerEvent(contest_index=2, rating_mu=1312, rating_sig=111, perf_score=1393, place=1),
                            PyPlayerEvent(contest_index=3, rating_mu=1291, rating_sig=100, perf_score=1240, place=3),
                            PyPlayerEvent(contest_index=4, rating_mu=1279, rating_sig=94, perf_score=1247, place=3)]),
 'player_4': Player(name='player_4',
                    rating=1809,
                    events=[PyPlayerEvent(contest_index=3, rating_mu=1767, rating_sig=171, perf_score=1819, place=0),
                            PyPlayerEvent(contest_index=4, rating_mu=1809, rating_sig=130, perf_score=1855, place=0)])}
```

### Contributing

Welcome contributions! If you would like to contribute to the project, please fork the repository and submit a pull request.
