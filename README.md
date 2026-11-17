<p align="center">
  <img alt="vstack" src="assets/vstack-logo.svg" width="360">
</p>

<p align="center">
  <a href="https://haoailab.com/blogs/verifiable-llm-infra/"><b>Blog</b></a> ·
  <a href="https://docs.google.com/spreadsheets/d/1FL5QqgzEpja9k8Zw6GmIQDtHveddjj1coHe1MJ3Ts-Q/edit"><b>Verified AI Infra Bugs</b></a> ·
  <a href="https://github.com/hao-ai-lab/veriserve"><b>VeriServe</b></a> ·
  <a href="https://x.com/haoailab/status/2120595980659917024"><b>X</b></a>
</p>

`vstack` is a formal verification toolkit for coding agents. Naive agents routinely game formal checkers by weakening invariants, dropping timeout branches, or adding unverified assumptions; `vstack` enforces mechanical gates across TLA+, Apalache, TLAPS, and Z3 so agents find real bugs and prove critical state machines without cheating.

![vstack workflow](assets/vstack-anti-cheat.gif)

## News

- **[2026-11-17]** Shared 5 [SGLang](https://github.com/sgl-project/sglang) bug case studies and fix PRs on [X](https://x.com/haoailab/status/2122758544462434802), with 40+ bugs now tracked across SGLang and vLLM in our [bug tracker](https://docs.google.com/spreadsheets/d/1FL5QqgzEpja9k8Zw6GmIQDtHveddjj1coHe1MJ3Ts-Q/edit).
- **[2026-11-13]** Shared 5 [vLLM](https://github.com/vllm-project/vllm) bug case studies on [X](https://x.com/haoailab/status/2121320482876399825), with 15+ bugs tracked and growing in our [bug tracker](https://docs.google.com/spreadsheets/d/1FL5QqgzEpja9k8Zw6GmIQDtHveddjj1coHe1MJ3Ts-Q/edit).
- **[2026-11-11]** Released `vstack` along with our [blog post](https://haoailab.com/blogs/verifiable-llm-infra/), [VeriServe](https://github.com/hao-ai-lab/veriserve), and [launch X thread](https://x.com/haoailab/status/2120595980659917024).

## Quick Start

```bash
git clone https://github.com/hao-ai-lab/vstack.git && cd vstack
uv tool install -e .
vstack setup   # checks Java/TLC/Z3 and installs skills, agents and the docs they link to into Claude Code, Codex, or Cursor
```

Or install directly as a plugin in Claude Code via `/plugin marketplace add hao-ai-lab/vstack` and `/plugin install vstack`, or in Cursor via `/add-plugin vstack`.

Run `/vstack-mode` on a target module and safety property:

```text
/vstack-mode verify that our RDMA KV cache lease manager never recycles an in-flight page on timeout.
```

## Anti-Reward-Hacking Gates

| Gate | What It Enforces |
| :--- | :--- |
| **[Role isolation](docs/layer-0.md)** | Separate coordinator, worker, and red-team agents keep specs, modeling, and review independent. |
| **[Hash-pinned specs](docs/contracts.md)** | SHA-256 locks safety properties and theorem signatures so workers cannot weaken the goal. |
| **[Line-anchored models](docs/method-selection.md)** | Every state variable and action maps to an exact `file:line@commit` across TLC, Apalache, and Z3. |
| **[Mutation & trace gates](docs/gates.md)** | Models must fail on historical bugs, pass with the fix, fail when guards are removed, and [replay real traces](docs/trace-validation.md). |
| **[Exposure gate](docs/exposure-gate.md)** | A finding is reported as caught by formal checking only if a faithful model with every bug switch off violates a named property, a red team fails to refute it, and it reproduces on a real engine next to a passing control. Shell models, experiment-only failures and calibration runs do not count. |
| **Proof & runtime checks** | Critical state machines scale to unbounded TLAPS proofs with preconditions mirrored as runtime checks. |

The **[model adequacy readout](docs/model-adequacy.md)** is not a gate: it reports how closely a model follows its code (trace acceptance, historical fix coverage and blind detection recall, each with its denominator and interval) and sets no thresholds. Bug hunts report a light version; full verification and regression skills report all of it.

## Recommended Models

| Workflow Stage | Recommended Models | Why |
| :--- | :--- | :--- |
| **Modeling, Proofs & Red-Team** | `Fable 5.2`, `GPT-6.1-Sol`, `Gemini 4 Carbon` at high reasoning effort | Strongest at state-machine abstraction, inductive invariants, and catching missing guards. |
| **Code Analysis & Repro Harness** | `Claude Opus 5.5`, `Gemini 4 Carbon` | Fast and reliable at navigating large Python/CUDA codebases and building multi-GPU reproducers. |

## Case Studies

- **AI Infra Bug Hunting:** Concurrency, lifecycle, and numerical bugs uncovered across [SGLang](https://github.com/sgl-project/sglang) ([X case studies](https://x.com/haoailab/status/2122758544462434802)) and [vLLM](https://github.com/vllm-project/vllm) ([X case studies](https://x.com/haoailab/status/2121320482876399825)), tracked in [Verified AI Infra Bugs](https://docs.google.com/spreadsheets/d/1FL5QqgzEpja9k8Zw6GmIQDtHveddjj1coHe1MJ3Ts-Q/edit) and synced from [`bugs/verified-bugs.csv`](bugs/verified-bugs.csv) with `Prior Status` separating net-new (`Unknown`) discoveries from partly tracked (`Partly Known`) and independently caught unfixed upstream bugs (`Known`).
- **Community Verification:** Reproduce an `In Progress` candidate on hardware, validate an open fix PR, or contribute a new formally caught infra bug via PR to [`bugs/`](bugs/README.md) to be credited under **`Human Verifier`**.
- **[VeriServe](https://github.com/hao-ai-lab/veriserve):** A Prefill-Decode serving engine built with `vstack`, proved across 226 TLAPS modules with +0.18% average p50 TPOT overhead on NVIDIA GB200.

## Contributors

<p>
  <a href="https://github.com/yuxuandexter"><img src="assets/contributors/yuxuandexter.png" width="56" alt="Yuxuan Zhang" title="Yuxuan Zhang (@yuxuandexter)"></a>&nbsp;
  <a href="https://github.com/alexzms"><img src="assets/contributors/alexzms.png" width="56" alt="Minshen Zhang" title="Minshen Zhang (@alexzms)"></a>&nbsp;
  <a href="https://github.com/Davids048"><img src="assets/contributors/Davids048.png" width="56" alt="Junda Su" title="Junda Su (@Davids048)"></a>&nbsp;
  <a href="https://github.com/Boreas618"><img src="assets/contributors/Boreas618.png" width="56" alt="Yi Sun" title="Yi Sun (@Boreas618)"></a>&nbsp;
  <a href="https://github.com/GindaChen"><img src="assets/contributors/GindaChen.png" width="56" alt="Junda Chen" title="Junda Chen (@GindaChen)"></a>
</p>

## Acknowledgments

Skill orchestration draws inspiration from Lauren Tan's [pstack](https://github.com/cursor/plugins/tree/main/pstack). Trace validation and proof gates build on lessons from [Specula](https://github.com/specula-org/Specula), [SysMoBench](https://github.com/specula-org/SysMoBench), and [TLAPS-Bench](https://github.com/specula-org/TLAPS-Bench). We thank the TLA+, Z3, SGLang, and vLLM communities.

## Citation

```bibtex
@misc{vstack2026,
  title        = {Towards Verifiable {LLM} Infra},
  author       = {Zhang, Yuxuan and Zhang, Minshen and Su, Junda and Sun, Yi and Chen, Junda and Zhang, Hao},
  year         = {2026},
  month        = nov,
  howpublished = {Hao AI Lab Blog},
  url          = {https://haoailab.com/blogs/verifiable-llm-infra/}
}
```

## License

MIT License — see [LICENSE](LICENSE) and [NOTICE.md](NOTICE.md).
