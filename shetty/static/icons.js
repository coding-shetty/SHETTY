const paths = {
  spark:
    '<path d="m12 3 2.5 6.5L21 12l-6.5 2.5L12 21l-2.5-6.5L3 12l6.5-2.5L12 3Z"/><path d="m20 2 .6 1.4L22 4l-1.4.6L20 6l-.6-1.4L18 4l1.4-.6L20 2Z"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  memory:
    '<path d="M7 4h10a3 3 0 0 1 3 3v10a3 3 0 0 1-3 3H7a3 3 0 0 1-3-3V7a3 3 0 0 1 3-3Z"/><path d="M9 8h6M9 12h6M9 16h3M1 8h3M1 16h3M20 8h3M20 16h3"/>',
  checklist:
    '<rect x="5" y="4" width="15" height="17" rx="3"/><path d="M9 2v4M16 2v4m-7 7 2 2 4-4"/>',
  activity: '<path d="M3 12h4l3-8 4 16 3-8h4"/>',
  settings:
    '<path d="m9.4 3-.6 2.1-1.8 1.1-2.1-.5-2.6 4.5 1.5 1.6v2.1l-1.5 1.6L4.9 20l2.1-.5 1.8 1.1.6 2.1h5.2l.6-2.1 1.8-1.1 2.1.5 2.6-4.5-1.5-1.6v-2.1l1.5-1.6-2.6-4.5-2.1.5-1.8-1.1-.6-2.1H9.4Z" transform="translate(0 -1) scale(1 .94)"/><circle cx="12" cy="11.5" r="3"/>',
  shield:
    '<path d="m12 3 8 3v6c0 4.5-5 7.8-8 9-3-1.2-8-4.5-8-9V6l8-3Z"/><path d="m8.5 12 2.4 2.5 4.6-5"/>',
  "chevron-right": '<path d="m9 5 7 7-7 7"/>',
  "chevron-down": '<path d="m6 9 6 6 6-6"/>',
  arrow: '<path d="M5 12h14m-6-6 6 6-6 6"/>',
  "arrow-up": '<path d="M12 19V5m-6 6 6-6 6 6"/>',
  "arrow-up-right": '<path d="M6 18 18 6M6 6h12v12"/>',
  search: '<circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 5 5"/>',
  menu: '<path d="M4 6h16M4 12h16M4 18h16"/>',
  close: '<path d="m6 6 12 12M6 18 18 6"/>',
  chip: '<rect x="6" y="6" width="12" height="12" rx="3"/><path d="M9 1v5M15 1v5M9 18v5M15 18v5M1 9h5M1 15h5M18 9h5M18 15h5"/><rect x="10" y="10" width="4" height="4" rx=".5"/>',
  folder:
    '<path d="M3 7V5a2 2 0 0 1 2-2h5l3 3h6a2 2 0 0 1 2 2v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7Z"/><path d="M3 10h18"/>',
  globe:
    '<circle cx="12" cy="12" r="9"/><ellipse cx="12" cy="12" rx="4" ry="9"/><path d="M3 12h18"/>',
  window:
    '<rect x="3" y="3" width="18" height="18" rx="3"/><path d="M3 9h18M6 6h.01M9 6h.01"/>',
  monitor:
    '<rect x="3" y="3" width="18" height="13" rx="2"/><path d="M8 21h8m-4-5v5"/>',
  terminal: '<path d="m5 6 6 6-6 6M13 18h6"/>',
  lock: '<rect x="5" y="10" width="14" height="11" rx="2"/><path d="M8 10V7a4 4 0 0 1 8 0v3M12 14v3"/>',
  volume:
    '<path d="m11 4-6 5H2v6h3l6 5V4Zm5 4a6 6 0 0 1 0 8m3-11a10 10 0 0 1 0 14"/>',
  stop: '<rect x="6" y="6" width="12" height="12" rx="2"/>',
  clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
  refresh:
    '<path d="M20 8a8 8 0 0 0-14-3L3 8m0-5v5h5M4 16a8 8 0 0 0 14 3l3-3m0 5v-5h-5"/>',
  check: '<path d="m5 12 4 4L19 6"/>',
  trash: '<path d="M3 6h18M9 6V3h6v3M5 6l1 15h12l1-15M10 10v7M14 10v7"/>',
  edit: '<path d="m15 4 5 5M4 20l5-1L21 7a2 2 0 0 0-5-5L4 14v6Z"/>',
  note: '<path d="M14 3H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-9l-7-7Z"/><path d="M14 3v7h7M7 14h10M7 17h6"/>',
  sliders:
    '<path d="M4 6h16M4 12h16M4 18h16"/><rect x="7" y="4" width="3" height="4" rx="1"/><rect x="14" y="10" width="3" height="4" rx="1"/><rect x="8" y="16" width="3" height="4" rx="1"/>',
  bulb: '<path d="M9 18h6M9 21h6M9 15c0-3-4-3-4-7a7 7 0 0 1 14 0c0 4-4 4-4 7H9Z"/>',
  bell: '<path d="M6 9a6 6 0 0 1 12 0c0 7 3 7 3 9H3c0-2 3-2 3-9Zm4 12h4"/>',
  copy: '<rect x="8" y="8" width="13" height="13" rx="2"/><path d="M16 8V3H3v13h5"/>',
  info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v6M12 7h.01"/>',
  alert: '<path d="m12 3 10 18H2L12 3Z"/><path d="M12 9v5m0 3h.01"/>',
  moon: '<path d="M20.7 13a9 9 0 0 1-9.7-9.7A9 9 0 1 0 20.7 13Z"/>',
  link: '<path d="m9 15 6-6m-7 3-2 2a4 4 0 0 0 6 6l3-3m1-5 2-2a4 4 0 0 0-6-6L9 7"/>',
};
export function icon(name, className = "") {
  return `<svg class="icon ${className}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${paths[name] || paths.spark}</svg>`;
}
export function hydrateIcons(root = document) {
  root.querySelectorAll("[data-icon]").forEach((el) => {
    el.innerHTML = icon(el.dataset.icon);
  });
}
export const orb = `<svg class="shetty-orb" viewBox="0 0 180 180" fill="none" aria-hidden="true">
  <defs><radialGradient id="orb-fill"><stop stop-color="#b9ebc5" stop-opacity=".12"/><stop offset="1" stop-color="#b9ebc5" stop-opacity="0"/></radialGradient><linearGradient id="orb-line" x1="35" y1="25" x2="140" y2="155"><stop stop-color="#d8f7c7" stop-opacity=".8"/><stop offset=".5" stop-color="#a4d4b2" stop-opacity=".14"/><stop offset="1" stop-color="#a4d4b2" stop-opacity=".6"/></linearGradient></defs>
  <circle cx="90" cy="90" r="87" fill="url(#orb-fill)"/><circle cx="90" cy="90" r="75" stroke="#83968a" stroke-opacity=".16" stroke-dasharray="2 6"/><circle cx="90" cy="90" r="60" stroke="url(#orb-line)"/>
  <ellipse cx="90" cy="90" rx="30" ry="65" transform="rotate(40 90 90)" stroke="url(#orb-line)"/><ellipse cx="90" cy="90" rx="30" ry="65" transform="rotate(-40 90 90)" stroke="url(#orb-line)"/><ellipse cx="90" cy="90" rx="66" ry="26" stroke="url(#orb-line)"/>
  <circle cx="90" cy="90" r="35" fill="#151e18" stroke="#94b79c" stroke-opacity=".26"/><path d="m90 65 7 18 18 7-18 7-7 18-7-18-18-7 18-7 7-18Z" fill="#b9ebc5"/><circle cx="42" cy="42" r="3" fill="#b9ebc5"/><circle cx="151" cy="98" r="2" fill="#b9ebc5"/><path d="M90 4v7m0 158v7M4 90h7m158 0h7" stroke="#668471" stroke-opacity=".5"/>
</svg>`;
