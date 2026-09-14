const panel = document.querySelector(".chat-panel");
const messages = document.querySelector("[data-chat-messages]");
const form = document.querySelector("[data-chat-form]");
const history = [];

document.querySelectorAll("[data-chat-open]").forEach((button) => {
  button.addEventListener("click", () => {
    panel.classList.add("is-open");
    panel.setAttribute("aria-hidden", "false");
    panel.querySelector("textarea").focus();
  });
});

document.querySelector("[data-chat-close]")?.addEventListener("click", () => {
  panel.classList.remove("is-open");
  panel.setAttribute("aria-hidden", "true");
});

function addMessage(text, type) {
  const message = document.createElement("div");
  message.className = `message ${type}`;
  message.textContent = text;
  messages.appendChild(message);
  messages.scrollTop = messages.scrollHeight;
  return message;
}

form?.addEventListener("submit", async (event) => {
  event.preventDefault();
  const textarea = form.querySelector("textarea");
  const button = form.querySelector("button");
  const text = textarea.value.trim();
  if (!text || button.disabled) return;

  addMessage(text, "user");
  textarea.value = "";
  button.disabled = true;
  const pending = addMessage("Thinking…", "assistant pending");

  try {
    const response = await fetch(form.dataset.endpoint || "/api/chat/", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": document.querySelector('meta[name="csrf-token"]').content,
      },
      body: JSON.stringify({ message: text, history }),
    });
    const payload = await response.json();
    pending.textContent = response.ok ? payload.answer : payload.error;
    pending.classList.remove("pending");
    if (response.ok) {
      history.push(
        { role: "user", content: text },
        { role: "assistant", content: payload.answer.slice(0, 4000) },
      );
      history.splice(0, Math.max(0, history.length - 6));
    }
    messages.scrollTop = messages.scrollHeight;
  } catch (_error) {
    pending.textContent = "The assistant could not be reached. Please try again.";
    pending.classList.remove("pending");
  } finally {
    button.disabled = false;
    textarea.focus();
  }
});
