const previousPage = document.querySelector("[data-previous-page]");

if (previousPage && document.referrer && window.history.length > 1) {
  const previous = new URL(document.referrer);
  const current = window.location;
  const authPage = /^\/(?:login|signup)(?:\/|$)/;
  const isSignedIn = previousPage.dataset.signedIn === "true";
  const isAppPage = previous.origin === current.origin
    && !/^\/admin(?:\/|$)/.test(previous.pathname)
    && !(isSignedIn && authPage.test(previous.pathname));
  const isDifferentPage = previous.pathname !== current.pathname || previous.search !== current.search;

  if (isAppPage && isDifferentPage) {
    previousPage.closest("[data-page-navigation]").hidden = false;
    previousPage.addEventListener("click", (event) => {
      if (event.altKey || event.ctrlKey || event.metaKey || event.shiftKey) return;
      event.preventDefault();
      window.history.back();
    });
  }
}
