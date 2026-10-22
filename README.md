# KALQOR OS signed APT updates

Developed by Balaji Sangana.

Target source repository: https://github.com/kalqor-os/kalqor-update
Expected hosting URL AFTER enabling Pages: https://kalqor-os.github.io/kalqor-update/

This kit prepares the server content; it does not claim the Pages site is live. GitHub hosts the public APT files. Packages and release metadata are built and signed on your Debian workstation. No VPS, server account, GitHub Actions signing secret, or uploaded private key is needed.

## First publication on your existing Debian VM

1. Extract this ZIP into `~/Downloads/`. It creates `kalqor-update-setup/`.
2. Confirm your existing signing directory is `~/avuno-update-server/private/gnupg`. The default expected primary fingerprint is `A7D7859659871390C7CBEEEAAD422A07D0AAE677`, from your earlier Avuno archive. Renaming the OS does not require rotating this key. Its user ID may still say Avuno; the signed repository label says KALQOR.
3. Run as `tinku`, not root:

```bash
cd ~/Downloads/kalqor-update-setup
bash setup.sh
```

The script installs build tools, clones the exact source repository into `~/kalqor-update`, copies the reviewed builder and client scripts, creates a harmless `kalqor-release` package, exports ONLY the public key, signs the indexes, verifies the signatures, commits the public repository, and pushes `main`. It does not install the sample package or change OS identity.

If your key is elsewhere, set its private directory explicitly before setup:

```bash
export KALQOR_GNUPGHOME=/absolute/path/to/your/private/gnupg
bash setup.sh
```

Do not use a private-key file as that directory, and never put the private directory inside this source repository. If the expected key is absent, setup stops rather than generating a replacement silently.

If Git requires identity, set your name and the email you want in your public commits. Prefer the exact noreply email GitHub supplies in Settings -> Emails. Configure this inside `~/kalqor-update`, then rerun `./scripts/publish.sh`.

HTTPS pushes require an authorized token or credential manager, not your GitHub account password. The human GitHub account doing the push needs write permission to `kalqor-os/kalqor-update`; organization token approval may also be required. Never put the token in the repository URL, a script, or a public file.

## Enable GitHub Pages after the first push

Open https://github.com/kalqor-os/kalqor-update/settings/pages

- Source: Deploy from a branch.
- Branch: main.
- Folder: /docs.
- Save.

Wait for GitHub's Pages deployment to finish. The expected project URL is https://kalqor-os.github.io/kalqor-update/ unless your organization applies a custom domain or other Pages settings. Verify the actual URL GitHub returns.

The `.nojekyll` file is included in docs/. The whole docs/ directory must remain available; never publish just index.html.

## Connect a KALQOR client AFTER Pages is live

On the existing build workstation, from the reviewed checkout:

```bash
cd ~/kalqor-update
sudo bash scripts/install-client.sh
sudo apt install kalqor-release
cat /usr/share/kalqor/release-info
```

For another KALQOR machine, copy the reviewed `install-client.sh` to it through a trusted path, then run it with sudo. This script is NOT a curl-pipe-to-root installer.

The client script fetches the public key, compares the exact expected fingerprint, verifies InRelease, installs a dedicated `/etc/apt/keyrings/kalqor-archive.gpg`, and configures:

```text
Types: deb
URIs: https://kalqor-os.github.io/kalqor-update/
Suites: kalqor
Components: main
Architectures: amd64
Signed-By: /etc/apt/keyrings/kalqor-archive.gpg
```

APT preferences allow `kalqor-*` packages from this hosting origin and block other package names from that origin. Debian's original sources remain configured for Debian packages and security updates. Never use trusted=yes or disable signature checks.

Client configuration backups are created under `/var/backups/kalqor-apt-*`. If APT update fails, configuration remains for diagnosis; it does not silently switch to insecure transport or bypass checks.

## Publish subsequent updates

To verify version upgrades with a harmless new marker version:

```bash
cd ~/kalqor-update
./scripts/publish.sh --version 0.1.0~preview2
```

After Pages deploys, on a client:

```bash
sudo apt update
apt-cache policy kalqor-release
sudo apt install --only-upgrade kalqor-release
```

For a real custom package you built and reviewed:

```bash
./scripts/publish.sh --version 0.1.0~preview2 --add /absolute/path/kalqor-your-package_1.0_all.deb
```

Repeat `--add` for more packages. Only `kalqor-*`, amd64/all packages are accepted. A package cannot be overwritten with different content at an existing name/version/architecture: increase its version. Old package files and by-hash indexes are retained so prior indexes do not point at missing files.

Uploading a package provides an update path for clients that already have that package installed. New optional applications do not automatically install themselves. Wallpaper, branding, and custom settings need proper Debian packages and upgrade behavior before they become automatic OS updates. This starter does not copy your current home directory into a package.

## Metadata lifetime and operation

Release metadata expires 30 days after signing. Refresh and publish before then, even if no package changes are needed:

```bash
cd ~/kalqor-update
./scripts/publish.sh --version 0.1.0~preview2
```

Use the current marker version. A GitHub Pages web host cannot refresh a signature without the private key. This design deliberately keeps that key on your workstation; no automatic signing job is configured. Check the key's own expiration separately and plan renewals before clients lose update access.

Use GitHub Pages for the small custom archive, not a Debian mirror or ISO host. Pages' published site limit is 1 GB and soft bandwidth limit is 100 GB/month. This starter stops at 900 MiB total public files and 50 MiB per package; Git history also grows, so review retention as the project expands. No Git LFS pointers should appear in the package pool.

Keep Debian sources and existing update paths until the new channel has been verified. Migrate older Avuno-specific sources deliberately after testing; this kit does not delete them.

## Local validation of this kit

- Shell and Python syntax checked.
- Rebuilding an unchanged package version verified for reproducibility.
- Isolated APT accepted signed metadata and downloaded the marker package.
- Isolated APT rejected a changed package and altered signed metadata.

These tests used a disposable key and local files, not your production key or GitHub Pages. This execution environment cannot create GnuPG agent sockets, so the cryptographic integration tests used a temporary Sequoia signing adapter; gpgv and APT performed actual verification. The production script uses the standard GnuPG commands and verifies its generated signatures locally before any push. Your actual private-key access, Git push, Pages deployment, and HTTPS client update still need to complete on your VM.

## Files

- setup.sh: first-time workstation setup and initial push.
- scripts/build-repo.py: build package indexes, signatures, and public landing page.
- scripts/publish.sh: build, sign, commit, and push.
- scripts/install-client.sh: verify and add the signed client source.
- docs/: public archive, generated by the builder.
- .build/: local temporary files, ignored by Git.

No private key, personal home directory, or GitHub token is included in this ZIP.

## References

- https://manpages.debian.org/trixie/apt/apt-secure.8.en.html
- https://docs.github.com/en/pages/getting-started-with-github-pages/configuring-a-publishing-source-for-your-github-pages-site
- https://docs.github.com/en/pages/getting-started-with-github-pages/github-pages-limits
