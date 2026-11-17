# jacobstephens.net

Personal website of Jacob Stephens (https://jacobstephens.net). A lightweight, static HTML site with a standard-library Python post publisher and self-hosted fonts. Theme follows the OS light/dark preference by default; a fixed toggle in the top-right pins an explicit choice.

## Structure

```
├── index.html              # Homepage
├── posts/                  # Blog posts and colocated post-local assets
│   ├── index.html          # Posts listing
│   ├── bending-fire/
│   ├── on-sexuality-and-criminality/
│   ├── why-anti-cyrillic-croats-attack-serbian-language/
│   ├── two-natures-one-being/
│   ├── finding-greener-alternatives-to-ap-chromatography-lab/
│   └── the-heart-fragile-as-glass/
├── about/                  # About page
├── message/                # Contact page
├── privacy-policy/         # Privacy policy
├── styles/                 # CSS
│   ├── reset.css           # Meyer CSS reset
│   ├── style.css           # Site styles
│   └── theme.js            # Theme preference, initialization and toggle
├── fonts/                  # Self-hosted web fonts (Merriweather, Playfair Display)
├── static/                 # Legacy unmigrated media (registered posts use posts/<slug>/)
└── .htaccess               # Apache rewrites and redirects
```

## Theme authoring

Every HTML page using `/styles/style.css` includes the theme script exactly once,
synchronously in the head after charset/viewport metadata and before stylesheets:

```html
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <script src="/styles/theme.js"></script>
    <meta name="theme-color" content="#fef9ee">
    <link rel="stylesheet" href="/styles/reset.css">
    <link rel="stylesheet" href="/styles/style.css?v=23">
</head>
```

Keep preference logic in `styles/theme.js`; do not add an inline initializer or
`defer`, `async` or `type="module"` to the include. This applies to the archive,
drafts and model-council pages as well as published posts. Historical pages using
their own styles stay outside this contract.

The script reads the existing `theme` storage key once. Stored `light` or `dark`
pins override the system before styles apply; missing, invalid or inaccessible
storage follows the system. The in-page preference owns subsequent clicks and
events. Storage is best-effort: blocked or silently discarded writes cannot undo
a choice on the current page, though that choice may not survive navigation.
System changes apply in system mode; a storage event for `theme` accepts a new
pin or returns to system mode on removal/invalid values. Once the document is
ready, the script mounts the fixed accessible toggle and refreshes optional
theme-color metadata, then enables transitions on the next animation frame.

The synchronous classic script blocks rendering while its small asset loads on a
cold visit. This accepted trade-off applies stored pins before styled rendering
and keeps all preference policy in one place. If it fails to load, CSS still
follows the system, without a scripted toggle; add no copied fallback.

Theme tests require Node.js 18+ and Python 3.10+, using only their standard
libraries. There is no package install or production build step:

```sh
node --test tests/test_theme.cjs
python3 -m unittest discover -s tests -p test_theme.py -v
python3 -m unittest discover -s tests -v
python3 tools/publish.py check
```

## Adding a new post

1. Create `posts/my-new-post/index.html` using an existing post as a template.
   Use a unique lowercase hyphenated slug and exactly one complete `<head>`.
   Include at most one robots meta tag, directly inside the head; the publisher
   handles its contents and can insert it without a theme-color anchor.
   Colocate all post-specific images, PDFs, scripts, data files, and nested pages
   (such as `model-council/` and `model-council/sources/`) inside
   `posts/my-new-post/` rather than `/static/`, so draft gates protect every
   post asset alongside the post HTML. Reference post-local targets using
   relative paths inside `posts/my-new-post/`, root-relative
   `/posts/my-new-post/...` paths, or same-site
   `https://jacobstephens.net/posts/my-new-post/...` URLs (for example in
   `og:image` / `twitter:image`). Relative `..` segments may navigate within
   `posts/my-new-post/` (such as `../` from a nested page) but may not traverse
   outside the post directory. Shared site chrome (`/styles/...`, `/fonts/...`,
   `/icons/...`, `/favicon-32x32.png`), site routes (`/`, `/posts/`, `/about/`,
   `/projects/`, `/message/`, `/privacy-policy`), external URLs, and page links
   to registered `/posts/<other-slug>/` pages are allowed; `/static/` links,
   missing post-local targets, cross-post non-page assets, and path traversal
   outside `posts/my-new-post/` fail validation.
2. Register the post in `posts.json` with `slug`, nonempty `title` and `date`
   strings, a `categories` list of unique declared category ids, and `status`
   set to `draft`. An empty category list is valid. The array order controls
   listing order; display dates are preserved as text.
3. Run `python3 tools/publish.py build`, then `python3 tools/publish.py check`.
   Commit the manifest, post and generated changes together. Drafts are omitted
   from listings, carry `noindex, nofollow`, and get a generated `.htaccess`
   requiring the shared preview password via HTTP Basic Auth plus
   `<IfModule mod_headers.c>` `Header always set X-Robots-Tag "noindex, nofollow"`.
   Its credential file remains `/var/www/.htpasswd-drafts` on the server; never
   commit credentials.
4. To publish, run `python3 tools/publish.py publish my-new-post`, then `check`
   again and commit the changes. To return a post to draft, run
   `python3 tools/publish.py draft my-new-post` and check/commit again.

`python3 tools/publish.py` (or `list`) shows all registered posts;
`python3 tools/publish.py status my-new-post` shows one record. These commands
validate only the manifest, so they remain usable while repairing site markup.

Do not manually edit generated listing contents, robots directives or post gates.
Category headings and navigation remain authored. When adding a category, add its
safe id and nonempty label to the manifest's `categories` mapping, then add its
navigation link and a heading/list pair to the category view in `posts/index.html`:

```html
<section class="archive-view archive-view-category" id="by-category">
    <!-- Existing navigation and other category pairs stay here. -->
    <h3 class="archive-category-heading" id="new-category">New category</h3>
    <ul class="archive-list"></ul>
</section>
```

Keep exactly one `by-category` section, with each declared category heading and
its following list as direct children. Keep exactly one
`<section class="archive-view archive-view-chrono" id="chronological">` with
one direct `<ul class="archive-list">`. Attribute order, quoting and whitespace
may vary. The publisher replaces only list interiors and managed robots tags;
headings, navigation, prose and styling stay authored. Undeclared post directories
are outside the publisher's scope.

All reconciliation commands validate every registered post—including all HTML
files and post-local asset and link boundaries under each registered post
directory—alongside archive targets and existing gates before writing anything.
`check` is read-only and fails on invalid
input or stale output. `build` repairs drift; repeating it leaves files untouched.
Status changes reconcile the whole site in the same plan, creating draft gates
first, updating HTML and the manifest next, and removing published gates last.
Replacements are atomic per file and retain existing permissions. An operating
system write failure returns nonzero but may leave partial changes; repair the
reported cause, then run `build` and `check`. There is no multi-file rollback or
coordination with concurrent writers.

## Publishing tests

Python 3.10+ is required. Tests use only the standard library and disposable sites:

```sh
python3 -m unittest discover -s tests -v
python3 -m unittest discover -s tests -p test_publish.py -k transitions -v
python3 -m py_compile tools/publish.py tests/test_publish.py
python3 tools/publish.py build
python3 tools/publish.py check
```

## Deployment

Every push to `master` triggers `.github/workflows/deploy.yml`. The workflow
connects to the production server with a deploy-only SSH key whose server-side
entry is restricted to one forced command. That command validates the incoming
tree, fast-forwards the clean live checkout at `/var/www/jacobstephens.net`, and
runs `python3 tools/publish.py check` again after deployment.

The server-side command and its Ansible installation playbook live in the
`stephens-page-infra` repository. If a deployment fails, inspect the repository's
Actions tab; the deployer prints the failed safety check or command there.
