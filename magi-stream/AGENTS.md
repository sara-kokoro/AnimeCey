<!-- LOVABLE:BEGIN -->
> [!IMPORTANT]
> This project is connected to [Lovable](https://lovable.dev). Avoid rewriting
> published git history — force pushing, or rebasing/amending/squashing commits
> that are already pushed — as it rewrites history on Lovable's side and the
> user will likely lose their project history.
>
> Commits you push to the connected branch sync back to Lovable and show up in
> the editor, so keep the branch in a working state.
<!-- LOVABLE:END -->

- Pages live in src/pages and import navigation helpers from @/lib/router (TanStack-based shim) — keeps the ported app's logic unchanged without react-router-dom.
- App routes use `ssr: false` because auth and API calls read localStorage at module load.
