/**
 * Insère un morceau de code publicitaire (HTML + <script>) dans la page.
 * Les <script> ajoutés avec innerHTML ne s'exécutent pas : on les recrée un par un pour qu'ils tournent.
 */
export function mountAdCode(container: HTMLElement, html: string): void {
  const tpl = document.createElement("template");
  tpl.innerHTML = html.trim();
  container.appendChild(tpl.content);
  container.querySelectorAll("script").forEach((old) => {
    const fresh = document.createElement("script");
    for (const attr of Array.from(old.attributes)) fresh.setAttribute(attr.name, attr.value);
    fresh.text = old.text;
    old.replaceWith(fresh);
  });
}
