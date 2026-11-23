<div align="center">
<h1>Branch-Informed Priors for Symbolic Regression in Physics</h1>

<a href="writeup/main.pdf"><img src="https://img.shields.io/badge/Write--up-PDF-red" alt="Write-up PDF"></a>
<a href="https://jaysen-ma.github.io/physics-priors/data/catalog/index.html"><img src="https://img.shields.io/badge/Formula-ledger-blue" alt="Formula ledger"></a>

<p><em>The draft write-up covers the operator-frequency analysis. Held-out formula scoring is complete, and the paired PySR benchmark is in progress.</em></p>
</div>

## Overview

Scientific discovery involves finding laws that explain what we observe and make predictions we can test. Symbolic regression can help by proposing equations directly from measurements. Known physics equations give us a starting point. They show regularities in how mathematical operators are used, and a Bayesian prior gives us a way to use those regularities to guide the search for new equations. [Constantin et al. (2026)](https://arxiv.org/html/2408.11065v2)

Guimerà et al. (2020) built an expression prior from operator counts in 4,080 mathematical expressions. Bartlett et al. (2023) trained a language model on 161 scientific equations, mostly from physics, to learn how operators are arranged within an equation. [Guimerà et al. (2020)](https://arxiv.org/pdf/2004.12157) · [Bartlett et al. (2023)](https://arxiv.org/html/2304.06333v2)

Constantin et al. found that operator frequencies decline approximately exponentially with rank, with a slower decline for proposed inflationary potentials than for three broader physics collections. This raises the question we investigate. **When we know which branch of physics a problem comes from, can equations from that branch help us recover its form?** [Constantin et al. (2026)](https://arxiv.org/html/2408.11065v2)

We re-examine the inflationary gap and expand the Feynman corpus to compare operator usage across seven branches. We then compare two priors built from the same training equations. One pools the branches, while the other gives greater weight to patterns from the relevant branch. We test whether knowing the branch improves the scores assigned to held-out equations and whether it helps PySR recover their form from numerical data.

### Operator frequencies across physics collections

We fit exponential decay rates by least squares on the log frequencies and reproduce the lower inflationary estimate. Changing the treatment of physical constants and amplitude prefactors leaves much of the gap with the Feynman benchmark intact. A collection of proposed $f(R)$ gravity functions has a fitted rate close to the inflationary estimate. Fitted rates also vary across the seven Feynman branches.

![Fitted exponential decay rates for seven Feynman branches and five comparison collections, with individual bootstrap intervals](writeup/figures/beta_by_branch.png)

> *Circles show the seven Feynman branches, and diamonds show the five comparison collections. The bars are individual 95% intervals from 10,000 whole-equation bootstrap resamples.*

### Scoring held-out equations

A decay rate describes operator usage across a collection. To score individual equations, we use a Katz back-off model that learns how operators are arranged in expression trees. The pooled prior learns from 775 Feynman equations. At each node in the tree, the branch-informed prior averages the pooled model’s operator probabilities with those from a model trained on the relevant branch’s subset of those same equations.

**The branch-informed prior improved held-out formula scores by 0.33 nats per equation on average.** This comparison covers 193 formulas across seven equally weighted branches, with a descriptive 95% interval of 0.08 to 0.59 nats. The clearest gains were in electromagnetism and quantum mechanics.

On the same split, blending once per equation gave a similar gain of 0.36 nats. Adding 34 equation families from other sources improved the pooled score and narrowed the branch-informed advantage in both adaptations we tested.

### Recovering equations from numerical data

The PySR benchmark compares the pooled prior with the original node-by-node blend. Both arms use the same data and search settings. The 177 held-out equations each have 1,000 noiseless observations and ten paired search seeds at 100 iterations per run, for 3,540 searches in total.

A run counts as successful when one of its three highest-ranked distinct candidates recovers the generating equation’s form. Algebraic equivalents count, and designated fitted coefficients may differ. The final comparison will report cases the symbolic checker cannot resolve separately.

## Limitations

- The operator-frequency analysis covers selected algebraic expressions and omits differential and integral forms. The fitted decay rates depend on the corpus and how expressions are represented. Rare operators produce flat tails that the exponential fit captures poorly.
- The held-out scores apply to this Feynman split. Follow-up comparisons reused the same test set and are exploratory.
- The numerical benchmark uses noiseless data, so recovery under measurement noise remains open.

## Evaluation

The expanded Feynman collection contains 1,016 expressions after deduplication, with 968 assigned to seven branches. The public formula ledger records the expressions, sources, counted trees and operator totals. [Formula ledger](https://jaysen-ma.github.io/physics-priors/data/catalog/index.html) · [Per-expression statistics](https://jaysen-ma.github.io/physics-priors/data/catalog/index.html?page=beta)

See the [reproduction guide](docs/reproduction.md) to run the operator-frequency analysis or view the formula ledger locally. The [development guide](docs/development.md) covers local tests and continuous integration.

## Acknowledgements

- **The Feynman Lectures on Physics**, Vol. I–III, R. P. Feynman, R. B. Leighton and M. Sands, New Millennium Edition, © California Institute of Technology, [feynmanlectures.caltech.edu](https://www.feynmanlectures.caltech.edu/). Extracted expressions record their source equation, volume, chapter and section.
- **AI Feynman benchmark**: S.-M. Udrescu and M. Tegmark, *AI Feynman: a physics-inspired method for symbolic regression*, Science Advances 6, eaay2631 (2020), as distributed with [arXiv:2408.11065](https://arxiv.org/abs/2408.11065).
- **Wikipedia**, [List of scientific equations named after people](https://en.wikipedia.org/wiki/List_of_scientific_equations_named_after_people) (CC BY-SA 4.0); each expression links to its article.
- **Encyclopaedia Inflationaris**: J. Martin, C. Ringeval and V. Vennin, Phys. Dark Univ. 5–6, 75 (2014), [arXiv:1303.3787](https://arxiv.org/abs/1303.3787).
- **Leemis**: L. M. Leemis and J. T. McQueston, *Univariate distribution relationships*, The American Statistician 62, 45 (2008); [chart](https://www.math.wm.edu/~leemis/chart/UDR/UDR.html).
- **f(R)**: T. P. Sotiriou and V. Faraoni, *f(R) theories of gravity*, Rev. Mod. Phys. 82, 451 (2010), [arXiv:0805.1726](https://arxiv.org/abs/0805.1726), and papers cited per expression in the ledger.
