# Deploying MDOS on free platforms

MDOS is one Python server (FastAPI with pandas, SciPy, statsmodels and scikit-learn) that also serves the web
interface, plus a database. Free plans split that into three roles:

| Role | What it does | Free choices that fit |
|---|---|---|
| Backend | Runs the MDOS container: API, statistics, agents | **Hugging Face Spaces** (Docker) |
| Database | Keeps projects, analyses and accounts | **Supabase Free** (PostgreSQL) |
| Front door (optional) | Serves the interface on your own domain and forwards `/api/*` to the backend | **Vercel**, **Netlify**, **Cloudflare Pages** |

The front door forwards the API instead of calling it from another site, so the browser sees one site and the
session cookie keeps its `SameSite=Strict` and `__Host-` protections. The front-door hosts send the same security
headers as the MDOS server (a test keeps them identical).

To let people try MDOS without any server, use the live demo on GitHub Pages instead: the whole app runs in the
visitor's browser and keeps projects there (see the "Project page" workflow). It suits trying MDOS, not team work,
because each browser has its own data.

## 1. Database: Supabase Free

1. Create a project at supabase.com and choose a strong database password.
2. Open **Connect** and copy the **Session pooler** connection string (it works over IPv4, which most free hosts
   need). Put your password in it (URL-encode characters such as `@`, `:` or `/`) and add `?sslmode=require`.
3. Use that string as `DATABASE_URL` on the backend. MDOS accepts the `postgresql://` form as it is and creates its
   tables on first start. The transaction pooler (port 6543) works too.

Free projects pause after a week without activity; open the Supabase dashboard to resume one. Keep the connection
string secret: it contains the database password.

## 2. Backend: Hugging Face Spaces (free CPU)

1. Publish the image once: push a version tag (for example `v0.1.0`) or run the **Container image** workflow from
   the Actions tab. Then, in GitHub, open **Packages, mdos, Package settings** and set the visibility to **Public**
   so the Space can pull it.
2. Create a Space with the **Docker** SDK (blank template). Upload the two files in
   [`deploy/huggingface/`](huggingface/): `README.md` and `Dockerfile`.
3. In the Space's **Settings, Variables and secrets**, add these as **secrets**:

   | Name | Value |
   |---|---|
   | `SECRET_KEY` | 48 or more random characters, for example from `python3 -c "import secrets; print(secrets.token_urlsafe(48))"` |
   | `DATABASE_URL` | The Supabase connection string from section 1 |
   | `ALLOWED_HOSTS` | `<owner>-<space>.hf.space` (the Space's direct address) |
   | `COOKIE_SECURE` | `true` |

4. Open `https://<owner>-<space>.hf.space` and create the first account; sign-up then closes. The Space page on
   huggingface.co shows an empty frame because MDOS refuses to be embedded in other sites; use the direct address.

Limits of the free Space: it sleeps when unused and starts again on the next visit, and its disk is wiped on
restart. Projects, analyses and accounts are safe in Supabase, but **uploaded data files are not kept**: keep your
original files, or use a host with a persistent disk (see `docs/13-deployment.md`).

## 3. Front door (optional): Vercel, Netlify or Cloudflare Pages

All three build the interface from the `frontend` folder and forward `/api/*` to the backend. Set the backend
address, for example `https://<owner>-<space>.hf.space`, in the environment variable `MDOS_BACKEND_URL` (https
only, no path). Then add the front door's domain to the backend's `ALLOWED_HOSTS` only if you see "Invalid host
header"; normally the backend sees its own host name.

| Host | Settings |
|---|---|
| **Vercel** | Import the repository, set **Root Directory** to `frontend`, add `MDOS_BACKEND_URL`. Build settings come from `frontend/vercel.json`. |
| **Netlify** | Import the repository, set **Base directory** to `frontend`, add `MDOS_BACKEND_URL`. Build settings come from `frontend/netlify.toml`. |
| **Cloudflare Pages** | Connect the repository, set **Root directory** to `frontend`, build command `npm ci --ignore-scripts && npm run build:dist && node scripts/static-host.mjs cloudflare`, output `dist`. Add `MDOS_BACKEND_URL` under **Settings, Variables**. The `/api` proxy is `frontend/functions/api/[[path]].js`. |

Behind a front door every visitor reaches the backend through the host's servers, so the backend sees one address
and the sign-in rate limit (10 per minute) is shared. Raise `RATE_LIMIT_AUTH_PER_MINUTE` on the backend if a team
signs in at the same time.

## 4. What does not fit, and why

| Platform | Status |
|---|---|
| **Firebase Spark (free)** | Firebase Hosting can forward requests only to Cloud Run or Cloud Functions, which need the paid Blaze plan. On Blaze, run the container on Cloud Run and add a Hosting rewrite from `/api/**` to it. On Spark, use Vercel, Netlify or Cloudflare Pages as the front door instead. |
| **Glitch** | Glitch stopped hosting apps in July 2025. |
| **Cloudflare D1** | D1 is SQLite that only Cloudflare Workers can reach. MDOS's server needs a PostgreSQL or SQLite connection of its own; use Supabase. |
| **Cloudflare R2** | R2 could hold uploaded files in a later version (it speaks the S3 protocol); version 0.1.0 stores files on the server's disk. |
| **Cloudflare KV** | Not needed: sessions are signed cookies, so there is nothing to keep in KV. |
| **Vercel, Netlify or Cloudflare as the backend** | Their functions cannot hold MDOS's scientific Python stack (well over their size limits), keep background agent runs alive, or keep files; use them as the front door only. |

## 5. Safety checklist

* Keep `SECRET_KEY`, `DATABASE_URL` and `ANTHROPIC_API_KEY` in each platform's secret store, never in the
  repository or in build logs.
* Keep `ALLOW_REGISTRATION` empty so only the first account can sign up.
* The front-door proxy only ever calls the one https address in `MDOS_BACKEND_URL`.
* Read [SECURITY.md](../SECURITY.md) before opening MDOS to other people.
