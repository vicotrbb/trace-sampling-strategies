# Versioned research release

Version **1.8.0** is the first public GitHub release of this study. It continues the internal manuscript revision sequence. This Git history begins with the publication snapshot; it does not reconstruct or backdate earlier development history.

The named PDF, original research files, and every raw observation retain their verified bytes from the authoring artifact. Publication-specific files add documentation, citation metadata, component licenses, and distribution checks. `export-provenance.json` records the selected original hashes and exclusion categories. No workloads were added for publication.

## Download and verify

Download from [the v1.8.0 release](https://github.com/vicotrbb/trace-sampling-strategies/releases/tag/v1.8.0). It supplies the paper PDF, the complete research archive, `RELEASE.json`, `VERIFICATION.log`, and detached `SHA256SUMS`.

GitHub limits each release asset to less than 2 GiB. The complete archive is therefore distributed in numbered parts when necessary. Download all parts into one directory; GitHub CLI users can use:

```sh
gh release download v1.8.0 --repo vicotrbb/trace-sampling-strategies --dir trace-sampling-download
cd trace-sampling-download
shasum -a 256 -c SHA256SUMS
cat trace-sampling-strategies-v1.8.0.tar.gz.part-* > trace-sampling-strategies-v1.8.0.tar.gz
python3 - <<'PY'
import hashlib, json
from pathlib import Path
m = json.loads(Path('RELEASE.json').read_text())['archive']
p = Path(m['name'])
with p.open('rb') as f:
    assert hashlib.file_digest(f, 'sha256').hexdigest() == m['sha256']
assert p.stat().st_size == m['bytes']
print('Combined archive: PASS')
PY
tar -xzf trace-sampling-strategies-v1.8.0.tar.gz
cd trace-sampling-strategies-v1.8.0
python3 release/verify.py
```

If a later release supplies a single `.tar.gz` file, skip the concatenation command. Use the exact part list in `RELEASE.json`; do not combine parts from different releases. The archive's internal `SHA256SUMS` covers its complete content except the manifest itself. The detached release manifest covers the uploaded parts, PDF, metadata, and validation log. `RELEASE.json` records the combined archive's digest and the exact Git commit.

The ordinary Git checkout omits `data/raw/` to keep cloning practical. Use `python3 release/verify.py --source-only` there. The release archive and Git tree share the same source files and inventory. The raw evidence belongs to the release assets, not Git LFS. GitHub's automatic source archives alone are insufficient for raw-data reconstruction.

## Reproduce the artifact

The main README gives the environment and analysis commands. `make verify-current` checks the named paper and source package, recomputes the latest paired summaries and the localization Monte Carlo precision, checks the separate SDK comparison, and reconstructs the measured batching histograms. `make verify` runs the larger archived campaign validators. `make verify-proof` checks the limited Lean core.

Historical `verify_*revision.py` and document reports describe earlier presentation snapshots. Some rely on local editorial backups omitted from public distribution. They are retained as research history; the public release entry points are `release/verify.py`, `make verify-current`, and the data validators in `make verify`.

To rebuild the complete archive from an unchanged full release tree, use `python3 release/build_bundle.py --output /path/to/a/new/directory`. It refuses to overwrite an existing directory. The packaging step does not publish anything. The release process separately verifies a fresh extraction, records the validation log, checks remote asset digests, and publishes an immutable GitHub release after all uploads complete.

Checksums and release immutability establish which bytes were distributed. They do not establish universal scientific validity, external replication, or archival DOI registration. There is no Zenodo or arXiv deposit claimed by this GitHub release.
