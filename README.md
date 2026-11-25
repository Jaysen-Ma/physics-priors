<div align="center">
<h1>Branch-Informed Priors for Symbolic Regression in Physics</h1>

<a href="writeup/main.pdf"><img src="https://img.shields.io/badge/Write--up-Draft%20PDF-red" alt="Write-up draft PDF"></a>
<a href="https://jaysen-ma.github.io/physics-priors/data/catalog/index.html"><img src="https://img.shields.io/badge/Formula-ledger-blue" alt="Formula ledger"></a>

<p><strong>Work in progress.</strong> The write-up is an unfinished draft.</p>
</div>

## Overview

Bayesian symbolic regression uses a prior to express which equation forms are plausible before considering the data, and such a prior can be learned from a curated collection of scientific equations. [Guimerà et al. (2020)](https://doi.org/10.1126/sciadv.aav6971) · [Bartlett et al. (2023)](https://doi.org/10.1145/3583133.3596327)

In physics, ranked operator frequencies have been found to decline more slowly in a collection of inflationary potentials than in broader physics collections. This raises the question of whether physics equations have different statistical signatures across domains, which might explain the difference in decay rates. [Constantin et al. (2026)](https://doi.org/10.1098/rsta.2025.0091)

We revisit the gap using direct log least squares, a computationally simpler approach than training a simulation-based estimator. The gap persists after changes to constant conventions. To analyse a larger collection of expressions, we expand the Feynman collection to 1,016 expressions. We also build a corpus of 37 expressions for proposed $f(R)$ modified-gravity models and include 76 formulas from Wikipedia’s list of scientific equations named after people and 70 potentials from *Encyclopaedia Inflationaris*.

We created a public formula ledger for searching expressions, tracing their sources, inspecting expression trees and operator counts, and exploring plots of decay rate against complexity. [Formula ledger](https://jaysen-ma.github.io/physics-priors/data/catalog/index.html)

We estimate exponential decay rates and nominal 95% bootstrap intervals for the collections and branches. The $f(R)$ collection has a fitted rate close to that of the inflationary potentials, and the cause of the gap remains open. The Feynman estimates suggest that the decay rate varies across branches of physics.

Variation in operator use motivates asking whether adapting a symbolic regression prior to a specific branch gives more probability to the functional forms of equations from that branch. We use Codex to assign labels from each Feynman expression and its source context. Of the 1,016 expressions, 967 have a label in one of the seven physics branches and 221 have multiple labels. [Branch labels](data/catalog/feynman_branches.json)

We use grouped six-fold cross-validation on 943 Feynman formulas to compare a pooled prior with priors that use branch information. The branch-dependent prior trained with multiple labels assigns 1.34 times as much probability as the pooled prior on a geometric-average basis. These results measure how well the priors describe held-out expressions. [Saved results](results/prior_scoring/summary.json)

![Fitted exponential decay rates for seven Feynman branches and five comparison collections, with individual bootstrap intervals](writeup/figures/beta_by_branch.png)

*The bars show nominal 95% bootstrap intervals for individual fits. The branch estimates use the Codex labels.*

## Explore and reproduce

The reproduction guide covers rebuilding the catalogues, generating the decay-rate figures and repeating the prior comparison. The development guide covers tests and continuous integration. [Reproduction guide](docs/reproduction.md) · [Development guide](docs/development.md) · [TeX source](writeup/main.tex)

## Acknowledgements

- **The Feynman Lectures on Physics**, Vol. I–III, R. P. Feynman, R. B. Leighton and M. Sands, New Millennium Edition, © California Institute of Technology, [feynmanlectures.caltech.edu](https://www.feynmanlectures.caltech.edu/). Extracted expressions record their source equation, volume, chapter and section.
- **AI Feynman benchmark**: S.-M. Udrescu and M. Tegmark, *AI Feynman: a physics-inspired method for symbolic regression*, Science Advances 6, eaay2631 (2020), as distributed with [arXiv:2408.11065](https://arxiv.org/abs/2408.11065).
- **Wikipedia**, [List of scientific equations named after people](https://en.wikipedia.org/wiki/List_of_scientific_equations_named_after_people) (CC BY-SA 4.0); each expression links to its article.
- **Encyclopaedia Inflationaris**: J. Martin, C. Ringeval and V. Vennin, Phys. Dark Univ. 5–6, 75 (2014), [arXiv:1303.3787](https://arxiv.org/abs/1303.3787).
- **Leemis**: L. M. Leemis and J. T. McQueston, *Univariate distribution relationships*, The American Statistician 62, 45 (2008); [chart](https://www.math.wm.edu/~leemis/chart/UDR/UDR.html).
- **f(R)**: T. P. Sotiriou and V. Faraoni, *f(R) theories of gravity*, Rev. Mod. Phys. 82, 451 (2010), [arXiv:0805.1726](https://arxiv.org/abs/0805.1726), and papers cited per expression in the ledger.
