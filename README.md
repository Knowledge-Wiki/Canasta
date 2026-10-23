# Knowledge-Wiki Canasta

This is the Knowledge-Wiki fork of [CanastaWiki/Canasta](https://github.com/CanastaWiki/Canasta).
It owns the patched Canasta image build; Kubernetes deployment repositories use
the resulting image by digest. See the [fork build and release guide](knowledge-wiki/README.md)
for the PHP patch, startup behavior, public download checks and update process.

The `knowledge-wiki` branch contains the maintained patch release. The upstream
description follows.

## Canasta
Canasta is a full-featured MediaWiki stack for easy deployment of enterprise-ready MediaWiki on production environments. It is "A comfy home for your knowledge"!

This repository is just one of the repositories for the Canasta distribution, and arguably not the main one (that would be [CanastaBase](https://github.com/CanastaWiki/CanastaBase), the base layer for this Canasta repository, and the one that holds MediaWiki and all its dependencies). This Canasta repository adds on to CanastaBase a set of over 170 extensions and skins.

For more information on Canasta, for both users and developers, see the Canasta homepage at https://canasta.wiki/.
