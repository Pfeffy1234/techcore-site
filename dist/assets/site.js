(function () {
  const modal = document.getElementById("certificate-modal");
  const modalBody = document.getElementById("modal-body");
  const modalTitle = document.getElementById("modal-title");
  const modalDownload = document.getElementById("modal-download");
  let lastFocus = null;

  function closeModal() {
    if (!modal) return;
    modal.hidden = true;
    modalBody.innerHTML = "";
    document.body.style.overflow = "";
    if (lastFocus && typeof lastFocus.focus === "function") {
      lastFocus.focus();
    }
  }

  function openModal(href, mime, title) {
    if (!modal || !href) return;
    lastFocus = document.activeElement;
    modalTitle.textContent = title || "Zeugnis";
    modalDownload.href = href;
    modalDownload.hidden = false;

    if (mime && mime.startsWith("image/")) {
      const img = document.createElement("img");
      img.src = href;
      img.alt = title || "Arbeitszeugnis";
      modalBody.replaceChildren(img);
    } else {
      const frame = document.createElement("iframe");
      frame.src = href;
      frame.title = title || "Arbeitszeugnis";
      modalBody.replaceChildren(frame);
    }

    modal.hidden = false;
    document.body.style.overflow = "hidden";
    modal.querySelector(".modal-close").focus();
  }

  document.querySelectorAll(".station-card.has-certificate").forEach((card) => {
    card.addEventListener("click", () => {
      openModal(card.dataset.certificate, card.dataset.mime, card.dataset.title);
    });
    card.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        openModal(card.dataset.certificate, card.dataset.mime, card.dataset.title);
      }
    });
  });

  modal?.querySelectorAll("[data-close-modal]").forEach((el) => {
    el.addEventListener("click", closeModal);
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && modal && !modal.hidden) {
      closeModal();
    }
  });
})();
