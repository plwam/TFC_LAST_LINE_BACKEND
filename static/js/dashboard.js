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
   * Retour visuel d'un bouton « copier » de bloc de code : on remplace l'icône par une coche, on
   * teinte le bouton en vert et on annonce « Copié » aux lecteurs d'écran, puis on restaure
   * l'état initial après 2 s.
   */
  function flashCopied(button) {
    const icon = button.querySelector("[data-copy-icon]");
    const check = button.querySelector("[data-copy-check]");
    const label = button.querySelector("[data-copy-label]");
    button.classList.remove("text-g-muted");
    button.classList.add("text-green-400");
    if (icon) icon.classList.add("hidden");
    if (check) check.classList.remove("hidden");
    if (label) label.textContent = "Copié";
    window.setTimeout(() => {
      button.classList.add("text-g-muted");
      button.classList.remove("text-green-400");
      if (icon) icon.classList.remove("hidden");
      if (check) check.classList.add("hidden");
      if (label) label.textContent = "Copier le code";
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
        copyText(target.value || target.textContent || "", status);
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
            copyBtn.onclick = () => copyText(data.secret_key, status);
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
    initSecretReveal();
    initConfirmByTyping();
    initFlashMessages();
  });
})();
