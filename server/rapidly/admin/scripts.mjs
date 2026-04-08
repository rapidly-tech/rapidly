// Rapidly backoffice — client-side JavaScript bundle entry point.
import htmx from "htmx.org";
import _hyperscript from "hyperscript.org";
import { EventSourcePlus } from "event-source-plus";

window.htmx = htmx;
_hyperscript.browserInit();

// ---------------------------------------------------------------------------
// CSRF — double-submit cookie pattern
// ---------------------------------------------------------------------------

function getCSRFToken() {
  const match = document.cookie.match(
    new RegExp("(?:^|;\\s*)_csrf_token=([^;]*)"),
  );
  return match ? decodeURIComponent(match[1]) : "";
}

// Attach the CSRF token header to every HTMX request automatically.
// Listening on `document` rather than `document.body` because the script
// is loaded in <head> before the body exists.
document.addEventListener("htmx:configRequest", (event) => {
  event.detail.headers["X-CSRF-Token"] = getCSRFToken();
});

const formPostSSE = (formElement, target) => {
  const eventSource = new EventSourcePlus(formElement.action, {
    method: formElement.method || "GET",
    headers: { "X-CSRF-Token": getCSRFToken() },
    body: new FormData(formElement),
    withCredentials: true,
    retryStrategy: "on-error",
  });
  const controller = eventSource.listen({
    onRequest() {
      formElement
        .querySelectorAll('button[type="submit"]')
        .forEach((button) => {
          button.disabled = true;
        });
    },
    onMessage(message) {
      htmx.swap(target, message.data, { swapStyle: "innerHTML" });
      if (message.event === "close") {
        controller.abort();
        formElement
          .querySelectorAll('button[type="submit"]')
          .forEach((button) => {
            button.disabled = false;
          });
      }
    },
    onResponse({ response }) {
      if (response.status === 422) {
        controller.abort();
        return;
      }
    },
  });
};

window.formPostSSE = formPostSSE;
