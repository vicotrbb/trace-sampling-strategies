# Trace Sampling at the Collector Boundary

**Costs and Diagnostic Evidence**

A measurement study and reproducibility artifact by **Victor Bona**.

[Zenodo preprint](https://zenodo.org/records/23032245) | [Read the paper](output/pdf/trace-sampling-collector-boundary.pdf) | [Download the complete evidence](https://github.com/vicotrbb/trace-sampling-strategies/releases/tag/v1.8.0) | [Citation](CITATION.cff) | [Release instructions](release/README.md)

Sampling reduces stored telemetry, but it does not necessarily reduce Collector CPU. This study measures how sampler placement, export path, and batching change the work saved, and how delivery mechanisms and sampling affect available diagnostic evidence.

At 40,000 offered spans/s, native uniform sampling at nominal 10% retention increased Collector CPU by 3.2% with JSON-only export and reduced it by 24.2% with JSON plus Jaeger. A low-load CPU reduction from retain-all tail processing disappeared in the higher-load batching experiment. The paper reports both outcomes and their measurement boundaries. Its localization example uses measured HTTP timings with ideal offline sampling, and is conditional on its task and fixed corpus.

The article is published as an open-access [Zenodo preprint](https://zenodo.org/records/23032245), version 1.8.0, with assigned DOI `10.5281/zenodo.23032245`. It has not been peer reviewed. Zenodo hosts the unchanged 22-page PDF, including the mathematical supplement as Appendix A; the complete evidence archive is hosted in the linked GitHub release. The manuscript and immutable release retain their preparation-time availability statements. See the [publication record](docs/ZENODO_PUBLICATION.md) for verification details and the DOI resolver status at publication.

## Read and inspect

| Path | Contents |
| :-- | :-- |
| [Paper PDF](output/pdf/trace-sampling-collector-boundary.pdf) | Named manuscript, references, and mathematical appendix. |
| [paper/](paper/) | LaTeX source, numerical inputs, and figures. |
| [data/derived/](data/derived/) | Resource intervals, paired contrasts, and localization summaries. |
| [docs/claim-evidence-map.md](docs/claim-evidence-map.md) | Claims and their evidence boundaries. |
| [docs/fifth-audit-20260928/](docs/fifth-audit-20260928/) | Latest protocols, freezes, pilot amendments, and validation records. |
| [experiments/](experiments/) | Workload harnesses and orchestration. |
| [scripts/](scripts/) | Evidence reconstruction and analysis. |
| [proofs/](proofs/) | Restricted Lean statements and written mathematical supplement. |
| [release/](release/) | Packaging, verification, provenance, and standalone preprint sources. |

The ordinary Git checkout contains source and derived results. The versioned release additionally supplies **all 9,242 raw evidence files**, including pilots, failed attempts, execution snapshots, and the retained measured campaigns. Download and reassemble the release parts as described in [release/README.md](release/README.md) before running raw-data checks. GitHub's automatically generated source ZIP and tarball do not contain `data/raw/`.

The public export omits private submission preparation, historical editorial backups, and downloaded third-party literature PDFs and web pages. Bibliographic citations, retrieval metadata, raw observations, source freezes, and original research code are retained. Some historical reports refer to omitted editorial files or caches; they describe their original snapshots, not the current release. The current public checks are the commands below. Anonymous submission materials remain separate from this named repository.

## Verify and reproduce

First verify the unmodified source checkout, using Python 3.11 or newer:

```sh
python3 release/verify.py --source-only
```

For the complete evidence archive, use `python3 release/verify.py` without `--source-only`. It checks every delivered file, all raw-file identities, the unchanged paper, and the six execution freezes. Integrity checks establish content identity, not independent replication or empirical validity.

Analysis was performed with Python 3.14. Workload runners use Python 3.12.10. Install the recorded analysis environment to recompute results:

```sh
python3.14 -m venv .venv
.venv/bin/pip install -r requirements.lock
make verify
make verify-current
make verify-proof
make analyze
make paper
```

`make verify` and `make verify-current` read the archived evidence and may update validation receipts. They do not run workloads or contact Kubernetes. Run integrity checks before analysis or rebuilding, or work in a disposable extracted copy. Complete span and input reconstruction can take substantially longer than PDF compilation. `make analyze` retains earlier analyses and renders the current presentation last. `make paper` needs a working LaTeX distribution and `latexmk`; rebuilt PDF metadata can differ from the sealed release PDF.

`make verify-proof` needs Lean 4.24.0. The six statements concern a restricted discrete model. They do not formalize the complete statistical argument, Collector behavior, or empirical conclusions. See [proofs/README.md](proofs/README.md).

The standalone [preprint source ZIP](release/preprint-source.zip) includes the mathematical appendix and ancillary Lean source. It can be compiled from `main.tex` without the research data. Its inclusion does not mean the paper has been submitted to arXiv.

## Study boundaries

The placement experiment has 40 cells in five randomized blocks. Other evidence includes 96 low-load fixed-input batching cells, 20 higher-load batching cells, an 80-cell load sweep, 60 live application cells, and matched delivery probes. The localization example uses a 600-incident corpus, nested 20/50/200-request windows, separate healthy calibration, and 5,000 replay trials per policy/budget comparison. Replay trials are not new observed incidents.

The study uses one shared node, loopback transport, Python generators, and OpenTelemetry Collector Contrib v0.136.0. Component CPU endpoints, process sums, serialization bytes, RSS, and trace retention remain distinct. A pre-ingress gate excludes selection work from the Collector endpoint. The higher-load batching point was limited by generator scheduling, not identified as Collector capacity. Results do not establish a universal safe sampling rate or human diagnostic performance. Failed or incomplete runs are retained and excluded from paired estimates as documented in the protocols.

The manuscript discloses its AI-assisted research workflow. Separate implementations and proof checks within that workflow are not external replication. Local freezes and checksums are not authenticated preregistration.

## Repeat workloads

Workload orchestration is explicitly separate from offline verification. Only run it on an authorized test cluster. The supplied wrappers target `kubectl --context homelab` and create isolated experiment namespaces; they are not deployment recommendations. The latest wrapper is `make homelab-fifth`. It writes a new timestamped archive, preserves failed attempts, and must not replace the released measurements. Its assembly and syntax were checked, but it has not itself produced a second complete campaign. Consult the protocols and wrapper before execution.

## Citation and licensing

For the article: Bona, V. (2026). *Trace Sampling at the Collector Boundary: Costs and Diagnostic Evidence* (Version 1.8.0) [Preprint]. Zenodo. https://doi.org/10.5281/zenodo.23032245

The direct [Zenodo record](https://zenodo.org/records/23032245) is publicly accessible. Use [CITATION.cff](CITATION.cff) and the [versioned release](https://github.com/vicotrbb/trace-sampling-strategies/releases/tag/v1.8.0) to identify the complete research artifact separately.

Original manuscript, data, figures, and narrative documentation are CC-BY-4.0. Original software and configuration are MIT. Third-party components retain their own terms. See [LICENSE.md](LICENSE.md) for the component-specific scope.
