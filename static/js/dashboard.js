/*
 * Interactions du tableau de bord — JavaScript vanilla, chargé en `defer` (06_FRONTEND_GUIDE.md §10).
 *
 * Règles :
 * - chaque fonction est inerte si ses éléments sont absents de la page (aucune erreur sur les
 *   pages qui ne les utilisent pas) ;
 * - jamais de `innerHTML` avec des données serveur (on utilise `textContent`) ;
 * - jamais de `eval`.
 */

(function () {
  "use strict";

  /** Lit le jeton CSRF exposé par la coquille (06_FRONTEND_GUIDE.md §2.1). */
  function getCsrfToken() {
    const body = document.body;
    if (body && body.dataset.csrf) return body.dataset.csrf;
    const meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? meta.getAttribute("content") : "";
  }

  /**
   * Tiroir de navigation mobile.
   * Pourquoi : la sidebar est masquée sous `lg`. On met à jour `aria-expanded` pour que les
   * lecteurs d'écran annoncent l'état, et on ferme sur Échap / clic extérieur / clic sur un lien.
   */
  function initSidebarToggle() {
    const toggle = document.querySelector("[data-sidebar-toggle]");
    const sidebar = document.getElementById("sidebar");
    if (!toggle || !sidebar) return;

    const close = () => {
      sidebar.classList.add("hidden");
      toggle.setAttribute("aria-expanded", "false");
    };
    const open = () => {
      sidebar.classList.remove("hidden");
      toggle.setAttribute("aria-expanded", "true");
    };

    toggle.addEventListener("click", () => {
      const isOpen = toggle.getAttribute("aria-expanded") === "true";
      isOpen ? close() : open();
    });
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape") close();
    });
    sidebar.querySelectorAll("a").forEach((link) => link.addEventListener("click", close));
  }

  /**
   * Copie un texte dans le presse-papiers avec repli si l'API moderne est indisponible.
   * `statusEl` (facultatif) reçoit un message temporaire ; `onSuccess` (facultatif) est appelé
   * UNIQUEMENT quand la copie a réussi (retour visuel d'un bouton, par exemple).
   */
  function copyText(text, statusEl, onSuccess) {
    const done = () => {
      if (statusEl) {
        const previous = statusEl.getAttribute("data-copied-label") || "";
        statusEl.textContent = "Copié ✓";
        window.setTimeout(() => {
          statusEl.textContent = previous;
        }, 2000);
      }
      if (typeof onSuccess === "function") onSuccess();
    };
    if (navigator.clipboard && window.isSecureContext) {
      navigator.clipboard.writeText(text).then(done).catch(() => fallbackCopy(text, done));
    } else {
      fallbackCopy(text, done);
    }
  }

  /**
   * Retour visuel d'un bouton « copier » (champ copiable, clé secrète, bloc de code) : on remplace
   * l'icône par une coche, on teinte le bouton en vert et on affiche « Copié » (visible et annoncé
   * aux lecteurs d'écran), puis on restaure l'état initial après 2 s.
   *
   * L'état de départ (couleur de texte + libellé) est mémorisé sur le bouton pour être restauré
   * fidèlement, quel que soit le composant d'origine.
   */
  function flashCopied(button) {
    const icon = button.querySelector("[data-copy-icon]");
    const check = button.querySelector("[data-copy-check]");
    const label = button.querySelector("[data-copy-label]");

    if (button.dataset.copiedBase === undefined) {
      const base = [];
      if (button.classList.contains("text-g-muted")) base.push("text-g-muted");
      if (button.classList.contains("text-g-blue")) base.push("text-g-blue");
      button.dataset.copiedBase = base.join(" ");
      if (label) button.dataset.copiedLabel = label.textContent;
    }
    const baseClasses = (button.dataset.copiedBase || "").split(" ").filter(Boolean);

    baseClasses.forEach((cls) => button.classList.remove(cls));
    button.classList.add("text-green-400");
    if (icon) icon.classList.add("hidden");
    if (check) check.classList.remove("hidden");
    if (label) label.textContent = "Copié";

    window.setTimeout(() => {
      button.classList.remove("text-green-400");
      baseClasses.forEach((cls) => button.classList.add(cls));
      if (icon) icon.classList.remove("hidden");
      if (check) check.classList.add("hidden");
      if (label) label.textContent = button.dataset.copiedLabel || "Copier";
    }, 2000);
  }

  /** Repli document.execCommand('copy') — utile sur une page servie en HTTP non sécurisé. */
  function fallbackCopy(text, done) {
    const area = document.createElement("textarea");
    area.value = text;
    area.setAttribute("readonly", "");
    area.style.position = "fixed";
    area.style.left = "-9999px";
    document.body.appendChild(area);
    area.select();
    try {
      document.execCommand("copy");
      done();
    } finally {
      document.body.removeChild(area);
    }
  }

  /** Boutons « Copier » sur un champ (data-copy-target) et sur un bloc de code (data-copy-code-target). */
  function initCopyButtons() {
    document.querySelectorAll("[data-copy-target]").forEach((button) => {
      button.addEventListener("click", () => {
        const target = document.getElementById(button.dataset.copyTarget);
        if (!target) return;
        const status = button.closest(".copy-field")?.querySelector("[data-copy-status]") ||
          button.parentElement.querySelector("[data-copy-status]");
        copyText(target.value || target.textContent || "", status, () => flashCopied(button));
      });
    });
    document.querySelectorAll("[data-copy-code-target]").forEach((button) => {
      button.addEventListener("click", () => {
        const target = document.getElementById(button.dataset.copyCodeTarget);
        if (target) copyText(target.textContent || "", null, () => flashCopied(button));
      });
    });
  }

  /**
   * Ouverture/fermeture des <dialog> natifs.
   * Le focus initial est sur « Annuler » (autofocus dans le gabarit) pour les actions
   * destructives : on évite une validation accidentelle par Entrée.
   */
  function initDialogs() {
    document.querySelectorAll("[data-dialog-open]").forEach((trigger) => {
      trigger.addEventListener("click", () => {
        const dialog = document.getElementById(trigger.dataset.dialogOpen);
        if (dialog && typeof dialog.showModal === "function") dialog.showModal();
      });
    });
    document.querySelectorAll("[data-dialog-close]").forEach((button) => {
      button.addEventListener("click", () => {
        const dialog = button.closest("dialog");
        if (dialog) dialog.close();
      });
    });
  }

  /**
   * Révélation de la clé secrète (06_FRONTEND_GUIDE.md §8.6.2).
   * - confirmation via un <dialog> (si présent) avant tout affichage ;
   * - POST fetch avec X-CSRFToken ;
   * - remasquage automatique après 30 s et effacement du nœud texte ;
   * - la valeur n'est jamais stockée dans un attribut, le localStorage ni l'URL.
   */
  function initSecretReveal() {
    const fields = document.querySelectorAll("[data-secret-field]");
    if (!fields.length) return;
    const dialog = document.getElementById("reveal-secret-dialog");

    const reveal = (field) => {
      const code = field.querySelector("[data-secret-value]");
      const copyBtn = field.querySelector("[data-secret-copy]");
      const status = field.querySelector("[data-secret-status]");
      fetch(field.dataset.revealUrl, {
        method: "POST",
        headers: { "X-CSRFToken": getCsrfToken(), "X-Requested-With": "XMLHttpRequest" },
        credentials: "same-origin",
      })
        .then((response) => {
          if (!response.ok) throw new Error("HTTP " + response.status);
          return response.json();
        })
        .then((data) => {
          if (!data.secret_key) throw new Error("Réponse invalide");
          code.textContent = data.secret_key;
          if (copyBtn) {
            copyBtn.hidden = false;
            copyBtn.onclick = () => copyText(data.secret_key, status, () => flashCopied(copyBtn));
          }
          if (status) status.textContent = "Clé affichée pendant 30 secondes.";
          window.setTimeout(() => {
            code.textContent = field.dataset.masked || "";
            if (copyBtn) copyBtn.hidden = true;
            if (status) status.textContent = "Clé masquée à nouveau.";
          }, 30000);
        })
        .catch(() => {
          if (status) status.textContent = "Impossible d'afficher la clé. Réessayez.";
        });
    };

    fields.forEach((field) => {
      const revealBtn = field.querySelector("[data-secret-reveal]");
      if (!revealBtn) return;
      revealBtn.addEventListener("click", () => {
        if (dialog && typeof dialog.showModal === "function") {
          dialog.dataset.targetField = field.id || "";
          dialog.showModal();
        } else {
          reveal(field);
        }
      });
    });

    if (dialog) {
      const confirmBtn = dialog.querySelector("[data-secret-confirm]");
      if (confirmBtn) {
        confirmBtn.addEventListener("click", () => {
          dialog.close();
          const field = dialog.dataset.targetField ? document.getElementById(dialog.dataset.targetField) : null;
          if (field) reveal(field);
        });
      }
    }
  }

  /**
   * Alerte pour les actions dangereuses (suspendre, désactiver…).
   *
   * Un formulaire portant `data-confirm` (et, à défaut, un lien `data-confirm-link`) est
   * intercepté : au lieu de s'exécuter immédiatement, il ouvre la fenêtre `#confirm-action-dialog`
   * partagée. La confirmation rejoue l'action (soumission du formulaire ou navigation du lien).
   *
   * Le texte par défaut est surchargé par `data-confirm-title`, `data-confirm-message` et
   * `data-confirm-label`. Purement dissuasif : la validation réelle reste côté serveur.
   */
  function initConfirmActions() {
    const dialog = document.getElementById("confirm-action-dialog");
    if (!dialog) return;
    const titleEl = dialog.querySelector("[data-confirm-title]");
    const messageEl = dialog.querySelector("[data-confirm-message]");
    const acceptBtn = dialog.querySelector("[data-confirm-accept]");
    const defaultTitle = titleEl ? titleEl.textContent : "";
    const defaultMessage = messageEl ? messageEl.textContent : "";
    const defaultLabel = acceptBtn ? acceptBtn.textContent : "";

    let pending = null; // { kind: "form" | "link", el } en attente de confirmation.

    const proceed = () => {
      if (!pending) return;
      const { kind, el } = pending;
      pending = null;
      if (kind === "form") {
        el.dataset.confirmed = "1";
        el.submit(); // `submit()` natif : ne redéclenche pas l'événement `submit`.
      } else {
        window.location.href = el.href;
      }
    };

    const open = (kind, el) => {
      pending = { kind, el };
      if (titleEl) titleEl.textContent = el.dataset.confirmTitle || defaultTitle;
      if (messageEl) messageEl.textContent = el.dataset.confirmMessage || defaultMessage;
      if (acceptBtn) acceptBtn.textContent = el.dataset.confirmLabel || defaultLabel;
      if (typeof dialog.showModal === "function") dialog.showModal();
      else proceed(); // Repli : pas de <dialog> supporté, on n'entrave pas l'action.
    };

    document.querySelectorAll("form[data-confirm]").forEach((form) => {
      form.addEventListener("submit", (event) => {
        if (form.dataset.confirmed === "1") return;
        event.preventDefault();
        open("form", form);
      });
    });
    document.querySelectorAll("a[data-confirm-link]").forEach((link) => {
      link.addEventListener("click", (event) => {
        if (link.dataset.confirmed === "1") return;
        event.preventDefault();
        open("link", link);
      });
    });

    if (acceptBtn) {
      acceptBtn.addEventListener("click", () => {
        proceed(); // Lit `pending` AVANT de fermer (le `close` le réinitialise).
        dialog.close();
      });
    }
    // Annulation (bouton « Annuler », Échap, clic extérieur) : on oublie l'action en attente.
    dialog.addEventListener("close", () => {
      pending = null;
    });
  }

  /**
   * Confirmation par recopie (suppression de projet / compte).
   * Active le bouton destructeur seulement quand la saisie correspond à la valeur attendue.
   * Purement cosmétique : la vérification réelle est côté serveur.
   */
  function initConfirmByTyping() {
    document.querySelectorAll("[data-confirm-submit]").forEach((button) => {
      const form = button.closest("form");
      if (!form) return;
      const input = form.querySelector('input[name="confirm"]');
      if (!input) return;
      const expected = button.dataset.confirmValue || "";
      const sync = () => {
        button.disabled = input.value.trim() !== expected;
      };
      input.addEventListener("input", sync);
      sync();
    });
  }

  /**
   * Flux temps réel du journal SDK (onglet « Journal SDK »).
   *
   * Le conteneur `[data-sdk-log-stream]` porte : `data-feed-url` (endpoint JSON), `data-since`
   * (horodatage ISO du dernier log connu), `data-live` (« 1 » = ajouter les nouvelles entrées en
   * tête) et `data-interval` (ms). On interroge l'endpoint en boucle ; on met à jour le badge
   * d'état ; si `live`, on préfixe les nouvelles entrées.
   *
   * Aucune donnée serveur n'est injectée via `innerHTML` : les cellules sont construites avec
   * `createElement`/`textContent` (règle 06 §10), donc un message contenant `<script>` s'affiche
   * littéralement sans jamais être exécuté.
   */
  function initSdkLogStream() {
    const root = document.querySelector("[data-sdk-log-stream]");
    if (!root) return;
    const url = root.dataset.feedUrl;
    if (!url) return;
    const interval = parseInt(root.dataset.interval, 10) || 8000;
    const live = root.dataset.live === "1";
    const tbody = root.querySelector("[data-log-rows]");
    let since = root.dataset.since || "";
    let inFlight = false;

    const cell = (text, className) => {
      const td = document.createElement("td");
      td.className = className;
      td.textContent = text;
      return td;
    };

    const badgeClass = (level) => {
      if (level === "error")
        return "inline-flex items-center rounded-full bg-red-500/15 px-2.5 py-0.5 text-xs font-medium text-red-300 ring-1 ring-inset ring-red-500/30";
      if (level === "warning")
        return "inline-flex items-center rounded-full bg-amber-500/15 px-2.5 py-0.5 text-xs font-medium text-amber-300 ring-1 ring-inset ring-amber-500/30";
      if (level === "debug")
        return "inline-flex items-center rounded-full bg-slate-500/15 px-2.5 py-0.5 text-xs font-medium text-slate-300 ring-1 ring-inset ring-slate-500/30";
      return "inline-flex items-center rounded-full bg-blue-500/15 px-2.5 py-0.5 text-xs font-medium text-blue-300 ring-1 ring-inset ring-blue-500/30";
    };

    const buildRow = (log) => {
      const tr = document.createElement("tr");
      tr.className = "border-t border-g-700 align-top hover:bg-g-800";
      tr.appendChild(cell(log.received_display || "", "whitespace-nowrap px-4 py-2 text-g-muted"));

      const levelTd = document.createElement("td");
      levelTd.className = "px-4 py-2";
      const badge = document.createElement("span");
      badge.className = badgeClass(log.level);
      badge.textContent = log.level_label || log.level || "";
      levelTd.appendChild(badge);
      tr.appendChild(levelTd);

      tr.appendChild(cell(log.kind_label || "", "px-4 py-2 text-g-muted"));

      const msgTd = document.createElement("td");
      msgTd.className = "px-4 py-2 text-g-text";
      const msg = document.createElement("div");
      msg.className = "break-words";
      msg.textContent = log.message || "—";
      msgTd.appendChild(msg);
      if (log.has_context && log.context_json) {
        const details = document.createElement("details");
        details.className = "mt-1";
        const summary = document.createElement("summary");
        summary.className = "cursor-pointer text-xs text-g-faint hover:text-g-muted";
        summary.textContent = "Contexte";
        const pre = document.createElement("pre");
        pre.className = "mt-1 whitespace-pre-wrap break-all rounded bg-g-800 p-2 text-xs text-g-muted";
        pre.textContent = log.context_json;
        details.appendChild(summary);
        details.appendChild(pre);
        msgTd.appendChild(details);
      }
      tr.appendChild(msgTd);

      tr.appendChild(cell(log.sdk_version || "—", "px-4 py-2 text-g-muted"));
      tr.appendChild(cell(log.session_label || "—", "px-4 py-2 text-g-muted"));
      return tr;
    };

    const updateStatus = (status) => {
      if (!status) return;
      root.querySelectorAll("[data-sdk-status] [data-sdk-state]").forEach((el) => {
        el.classList.toggle("hidden", el.dataset.sdkState !== status.state);
      });
      const hb = root.querySelector("[data-sdk-last-heartbeat]");
      if (hb && status.last_heartbeat_display) hb.textContent = status.last_heartbeat_display;
    };

    const prepend = (logs) => {
      if (!tbody || !logs.length) return;
      const fragment = document.createDocumentFragment();
      logs.forEach((log) => fragment.appendChild(buildRow(log)));
      tbody.insertBefore(fragment, tbody.firstChild);
      // Garde-fou : on ne laisse pas la table croître sans borne pendant une longue veille.
      while (tbody.children.length > 200) tbody.removeChild(tbody.lastElementChild);
    };

    const poll = () => {
      if (document.hidden || inFlight) return;
      inFlight = true;
      const query = since ? "?since=" + encodeURIComponent(since) : "";
      fetch(url + query, {
        headers: { "X-Requested-With": "XMLHttpRequest" },
        credentials: "same-origin",
      })
        .then((response) => (response.ok ? response.json() : Promise.reject(new Error("HTTP " + response.status))))
        .then((data) => {
          updateStatus(data.status);
          if (data.logs && data.logs.length) {
            if (live) prepend(data.logs);
            since = data.logs[0].received_at || since;
          }
        })
        .catch(() => {
          /* Réseau momentanément indisponible : on réessaiera au prochain cycle. */
        })
        .then(() => {
          inFlight = false;
        });
    };

    window.setInterval(poll, interval);
    // Un onglet redevient visible : on rafraîchit immédiatement plutôt que d'attendre le cycle.
    document.addEventListener("visibilitychange", () => {
      if (!document.hidden) poll();
    });
  }

  /**
   * Sommaire de documentation : suit la section visible pendant le défilement.
   * Le conteneur `[data-scrollspy]` porte les liens d'ancre ; la cible est l'élément dont
   * l'`id` correspond au fragment. On active le dernier titre passé sous la ligne de
   * flottaison, et le dernier lien quand le bas de page est atteint (sinon les sections
   * courtes en fin de page ne seraient jamais mises en évidence).
   */
  function initScrollSpy() {
    const nav = document.querySelector("[data-scrollspy]");
    if (!nav) return;

    const entries = Array.from(nav.querySelectorAll('a[href^="#"]'))
      .map((link) => {
        const id = link.hash.slice(1);
        const target = id ? document.getElementById(id) : null;
        return target ? { link, target } : null;
      })
      .filter(Boolean);
    if (!entries.length) return;

    const activeClasses = ["bg-g-800", "font-medium", "text-g-blue"];
    const idleClasses = ["text-g-muted"];
    let current = null;

    const revealInNav = (link) => {
      const top = link.offsetTop;
      const height = link.offsetHeight;
      if (top < nav.scrollTop) nav.scrollTop = Math.max(0, top - 8);
      else if (top + height > nav.scrollTop + nav.clientHeight) {
        nav.scrollTop = top + height - nav.clientHeight + 8;
      }
    };

    const activate = (entry) => {
      if (entry === current) return;
      if (current) {
        current.link.classList.remove(...activeClasses);
        current.link.classList.add(...idleClasses);
        current.link.removeAttribute("aria-current");
      }
      current = entry;
      if (!entry) return;
      entry.link.classList.remove(...idleClasses);
      entry.link.classList.add(...activeClasses);
      entry.link.setAttribute("aria-current", "location");
      revealInNav(entry.link);
    };

    const update = () => {
      // Ligne de flottaison sous l'en-tête : une section devient active dès qu'elle la franchit.
      const offset = 96;
      let visible = entries[0];
      for (const entry of entries) {
        if (entry.target.getBoundingClientRect().top <= offset) visible = entry;
        else break;
      }
      const atBottom =
        window.innerHeight + window.scrollY >= document.documentElement.scrollHeight - 2;
      activate(atBottom ? entries[entries.length - 1] : visible);
    };

    let pending = false;
    const schedule = () => {
      if (pending) return;
      pending = true;
      window.requestAnimationFrame(() => {
        pending = false;
        update();
      });
    };

    window.addEventListener("scroll", schedule, { passive: true });
    window.addEventListener("resize", schedule);
    update();
  }

  /** Fermeture des messages flash (les erreurs ne disparaissent jamais automatiquement). */
  function initFlashMessages() {
    document.querySelectorAll("[data-dismiss-alert]").forEach((button) => {
      button.addEventListener("click", () => {
        const alert = button.closest('[role="alert"], [role="status"]');
        if (alert) alert.remove();
      });
    });
  }

  document.addEventListener("DOMContentLoaded", () => {
    initSidebarToggle();
    initCopyButtons();
    initDialogs();
    initConfirmActions();
    initSecretReveal();
    initConfirmByTyping();
    initSdkLogStream();
    initScrollSpy();
    initFlashMessages();
  });
})();
