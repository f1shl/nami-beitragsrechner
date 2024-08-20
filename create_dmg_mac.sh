#!/bin/sh
# Create a folder (named dmg) to prepare our DMG in (if it doesn't already exist).
mkdir -p dist/dmg
# Empty the dmg folder.
rm -r dist/dmg/*
# Copy the app bundle to the dmg folder.
cp -r "dist/Nami Beitragsrechner.app" dist/dmg
# If the DMG already exists, delete it.
test -f "dist/Nami Beitragsrechner.dmg" && rm "dist/Nami Beitragsrechner.dmg"
create-dmg \
  --volname "Nami Beitragsrechner" \
  --volicon "img/favicon.icns" \
  --window-pos 200 120 \
  --window-size 600 300 \
  --icon-size 100 \
  --icon "Nami Beitragsrechner.app" 175 120 \
  --hide-extension "Nami Beitragsrechner.app" \
  --app-drop-link 425 120 \
  "dist/Nami Beitragsrechner.dmg" \
  "dist/dmg/"