#!/bin/bash
set -euo pipefail
[[ $EUID -eq 0 ]] || { echo 'Run this local, reviewed script with sudo.'; exit 1; }
[[ $(dpkg --print-architecture) == amd64 ]] || { echo 'This channel currently targets amd64 only.'; exit 1; }
BASE=https://kalqor-os.github.io/kalqor-update
EXPECTED=A7D7859659871390C7CBEEEAAD422A07D0AAE677
WORK=$(mktemp -d)
trap 'rm -rf -- "$WORK"' EXIT
mkdir -m 700 "$WORK/gnupg"
export GNUPGHOME="$WORK/gnupg"
curl --proto '=https' --tlsv1.2 -fsSL --connect-timeout 20 --max-time 90 \
  "$BASE/kalqor-archive-keyring.gpg" -o "$WORK/key.gpg"
ACTUAL=$(gpg --batch --show-keys --with-colons "$WORK/key.gpg" | awk -F: '$1=="fpr" {print $10; exit}')
[[ "$ACTUAL" == "$EXPECTED" ]] || { echo 'Signing-key fingerprint mismatch. No APT configuration changed.'; exit 1; }
curl --proto '=https' --tlsv1.2 -fsSL --connect-timeout 20 --max-time 90 \
  "$BASE/dists/kalqor/InRelease" -o "$WORK/InRelease"
gpgv --keyring "$WORK/key.gpg" "$WORK/InRelease"
BACKUP="/var/backups/kalqor-apt-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$BACKUP"
for file in /etc/apt/keyrings/kalqor-archive.gpg /etc/apt/sources.list.d/kalqor.sources /etc/apt/preferences.d/kalqor; do
    if [[ -e "$file" ]]; then cp -a --parents "$file" "$BACKUP/"; fi
done
install -d -m 755 /etc/apt/keyrings /etc/apt/sources.list.d /etc/apt/preferences.d
install -m 644 "$WORK/key.gpg" /etc/apt/keyrings/kalqor-archive.gpg
cat > /etc/apt/sources.list.d/kalqor.sources <<EOF
Types: deb
URIs: $BASE/
Suites: kalqor
Components: main
Architectures: amd64
Signed-By: /etc/apt/keyrings/kalqor-archive.gpg
EOF
cat > /etc/apt/preferences.d/kalqor <<'EOF'
Package: kalqor-*
Pin: origin "kalqor-os.github.io"
Pin-Priority: 500

Package: *
Pin: origin "kalqor-os.github.io"
Pin-Priority: -1
EOF
apt-get update -o Dir::Etc::sourcelist=/etc/apt/sources.list.d/kalqor.sources \
  -o Dir::Etc::sourceparts=- -o APT::Get::List-Cleanup=0
apt-cache policy kalqor-release
echo "Repository configured. Backups: $BACKUP"
echo 'Verify the candidate above, then run: sudo apt install kalqor-release'
