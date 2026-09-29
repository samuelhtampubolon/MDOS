# Third-party notices

Marketing Decision OS is Copyright © 2026 Samuel Hasudungan Tampubolon and released under the [MIT License](LICENSE).
It is built on the open-source components below.
Each component keeps its own license: the license texts ship inside the packages themselves (in the Docker image's
Python environment, in the desktop bundle and in `frontend/node_modules`) and at the source links listed here.
This list covers what the app ships; development and test tools (for example pytest, Ruff, Vite, Vitest and
Playwright) are used only to build and test it and are not redistributed.

## 1. Web interface (bundled into the built JavaScript and CSS)

| Component | Version | License | Source |
|---|---|---|---|
| @fontsource/ibm-plex-mono | 5.3.0 | OFL-1.1 | https://github.com/fontsource/font-files |
| @fontsource/ibm-plex-sans | 5.3.0 | OFL-1.1 | https://github.com/fontsource/font-files |
| @tanstack/query-core | 5.104.0 | MIT | https://github.com/TanStack/query |
| @tanstack/react-query | 5.104.0 | MIT | https://github.com/TanStack/query |
| cookie | 1.1.1 | MIT | https://github.com/jshttp/cookie |
| d3-array | 3.2.4 | ISC | https://github.com/d3/d3-array |
| d3-color | 3.1.0 | ISC | https://github.com/d3/d3-color |
| d3-format | 3.1.2 | ISC | https://github.com/d3/d3-format |
| d3-interpolate | 3.0.1 | ISC | https://github.com/d3/d3-interpolate |
| d3-path | 3.1.0 | ISC | https://github.com/d3/d3-path |
| d3-scale | 4.0.2 | ISC | https://github.com/d3/d3-scale |
| d3-shape | 3.2.0 | ISC | https://github.com/d3/d3-shape |
| d3-time | 3.1.0 | ISC | https://github.com/d3/d3-time |
| d3-time-format | 4.1.0 | ISC | https://github.com/d3/d3-time-format |
| internmap | 2.0.3 | ISC | https://github.com/mbostock/internmap |
| js-tokens | 4.0.0 | MIT | https://github.com/lydell/js-tokens |
| loose-envify | 1.4.0 | MIT | https://github.com/zertosh/loose-envify |
| react | 18.3.1 | MIT | https://github.com/facebook/react |
| react-dom | 18.3.1 | MIT | https://github.com/facebook/react |
| react-router | 7.18.4 | MIT | https://github.com/remix-run/react-router |
| react-router-dom | 7.18.4 | MIT | https://github.com/remix-run/react-router |
| scheduler | 0.23.2 | MIT | https://github.com/facebook/react |
| set-cookie-parser | 2.7.2 | MIT | https://github.com/nfriedly/set-cookie-parser |

**IBM Plex Sans and IBM Plex Mono** are Copyright 2017 IBM Corp., with Reserved Font Name "Plex", and are
distributed unmodified under the SIL Open Font License 1.1 (`node_modules/@fontsource/ibm-plex-sans/LICENSE`,
<https://openfontlicense.org>).

## 2. Server and desktop app (Python)

Exact versions are pinned with hashes in `backend/requirements.txt`; where two versions are listed, the one used
depends on the platform.

| Component | Version | License | Source |
|---|---|---|---|
| alembic | 1.20.0 | MIT | https://alembic.sqlalchemy.org |
| annotated-doc | 0.0.5 | MIT | https://github.com/fastapi/annotated-doc |
| annotated-types | 0.8.0 | MIT | https://github.com/annotated-types/annotated-types |
| anthropic | 1.9.0 | MIT | https://github.com/anthropics/anthropic-sdk-python |
| anyio | 4.15.1 | MIT | https://github.com/agronholm/anyio |
| argon2-cffi | 25.1.0 | MIT | https://github.com/hynek/argon2-cffi |
| argon2-cffi-bindings | 26.1.0 | MIT | https://github.com/hynek/argon2-cffi-bindings |
| cffi | 2.1.1 | MIT-0 | https://github.com/python-cffi/cffi |
| click | 8.5.0 | BSD-3-Clause | https://github.com/pallets/click/ |
| cloudpickle | 3.1.2 | BSD | https://github.com/cloudpipe/cloudpickle |
| defusedxml | 0.7.1 | PSF-2.0 | https://github.com/tiran/defusedxml |
| dnspython | 2.8.0 | ISC | https://www.dnspython.org |
| docstring-parser | 0.18.0 | MIT | https://github.com/rr-/docstring_parser |
| email-validator | 2.3.0 | Unlicense | https://github.com/JoshData/python-email-validator |
| et-xmlfile | 2.0.0 | MIT | https://foss.heptapod.net/openpyxl/et_xmlfile |
| fastapi | 0.141.1 | MIT | https://github.com/fastapi/fastapi |
| formulaic | 1.2.2 | MIT | https://github.com/matthewwardrop/formulaic |
| h11 | 0.16.0 | MIT | https://github.com/python-hyper/h11 |
| httpcore2 | 2.13.1 | BSD-3-Clause | https://github.com/pydantic/httpx2 |
| httptools | 0.8.0 | MIT | https://github.com/MagicStack/httptools |
| httpx2 | 2.13.1 | BSD-3-Clause | https://github.com/pydantic/httpx2 |
| httpx2-jsfetch | 1.0 | BSD-3-Clause | https://github.com/pydantic/httpx2 |
| idna | 3.20 | BSD-3-Clause | https://github.com/kjd/idna |
| interface-meta | 2.0.1 | MIT | https://github.com/matthewwardrop/interface_meta |
| jiter | 0.17.0 | MIT | https://github.com/pydantic/jiter/ |
| joblib | 1.6.0 | BSD-3-Clause | https://joblib.readthedocs.io |
| mako | 1.4.3 | MIT | https://www.makotemplates.org/ |
| markupsafe | 3.0.3 | BSD-3-Clause | https://github.com/pallets/markupsafe/ |
| narwhals | 2.26.0 | MIT | https://github.com/narwhals-dev/narwhals |
| numpy | 2.4.6 or 2.5.3 | BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0 | https://numpy.org |
| openpyxl | 3.1.5 | MIT | https://foss.heptapod.net/openpyxl/openpyxl |
| packaging | 26.3 | Apache-2.0 OR BSD-2-Clause | https://github.com/pypa/packaging |
| pandas | 3.0.6 | BSD | https://pandas.pydata.org |
| patsy | 1.0.3 | BSD | https://github.com/pydata/patsy |
| psycopg | 3.3.6 | LGPL-3.0-only | https://psycopg.org/ |
| psycopg-binary | 3.3.6 | LGPL-3.0-only | https://psycopg.org/ |
| pycparser | 3.0 | BSD-3-Clause | https://github.com/eliben/pycparser |
| pydantic | 2.13.5 | MIT | https://github.com/pydantic/pydantic |
| pydantic-core | 2.46.5 | MIT | https://github.com/pydantic |
| pydantic-settings | 2.15.0 | MIT | https://github.com/pydantic/pydantic-settings |
| pyjwt | 2.15.1 | MIT | https://github.com/jpadilla/pyjwt |
| python-dateutil | 2.9.0.post0 | BSD, Apache-2.0 | https://github.com/dateutil/dateutil |
| python-dotenv | 1.2.3 | BSD-3-Clause | https://github.com/theskumar/python-dotenv |
| python-multipart | 0.0.32 | Apache-2.0 | https://github.com/Kludex/python-multipart |
| pyyaml | 6.0.3 | MIT | https://github.com/yaml/pyyaml |
| scikit-learn | 1.9.1 | BSD-3-Clause | https://scikit-learn.org |
| scipy | 1.17.1 or 1.18.1 | BSD | https://scipy.org/ |
| six | 1.17.0 | MIT | https://github.com/benjaminp/six |
| sniffio | 1.3.1 | MIT / Apache-2.0 | https://github.com/python-trio/sniffio |
| sqlalchemy | 2.1.1 | MIT | https://www.sqlalchemy.org |
| starlette | 1.7.0 | BSD-3-Clause | https://github.com/Kludex/starlette |
| statsmodels | 0.15.0 | BSD-3-Clause | https://www.statsmodels.org |
| threadpoolctl | 3.7.0 | BSD-3-Clause | https://github.com/joblib/threadpoolctl |
| truststore | 0.10.4 | MIT | https://github.com/sethmlarson/truststore |
| typing-extensions | 4.16.0 | PSF-2.0 | https://github.com/python/typing_extensions |
| typing-inspection | 0.4.4 | MIT | https://github.com/pydantic/typing-inspection |
| tzdata | 2026.4 | Apache-2.0 | https://github.com/python/tzdata |
| uvicorn | 0.54.0 | BSD-3-Clause | https://uvicorn.dev/ |
| uvloop | 0.22.1 | Apache-2.0 / MIT | https://github.com/MagicStack/uvloop |
| watchfiles | 1.3.0 | MIT | https://github.com/samuelcolvin/watchfiles |
| websockets | 17.1 | BSD-3-Clause | https://github.com/python-websockets/websockets |
| wrapt | 2.5.0 | BSD-2-Clause | https://github.com/GrahamDumpleton/wrapt |

**psycopg** (the PostgreSQL driver of the cloud image) is licensed under the GNU Lesser General Public License 3.0.
MDOS uses it unmodified as a separately installed library that users can replace; its binary wheel also contains
libpq (PostgreSQL License) and OpenSSL (Apache-2.0). The desktop app uses SQLite and does not include psycopg.

## 3. Platforms

| Component | Where | License |
|---|---|---|
| Python 3.11 | Bundled in the desktop app; base of the Docker image | PSF-2.0 |
| PyInstaller bootloader | Starts the desktop app | GPL-2.0 with the bootloader exception, which allows distributing the result under any license |
| `python:3.11-slim` (Debian) | Docker runtime image | Each Debian package under its own license |
| `node:24-alpine` | Used only to build the web interface; not in the final image | MIT (Node.js) and Alpine package licenses |

To regenerate this file after changing dependencies, list the licenses from the installed package metadata
(`importlib.metadata` for Python, each `package.json` for npm) and update the tables.
