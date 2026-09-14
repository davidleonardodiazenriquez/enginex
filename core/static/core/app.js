const panel = document.querySelector(".chat-panel");
const messages = document.querySelector("[data-chat-messages]");
const form = document.querySelector("[data-chat-form]");

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
  if (!text) return;

  addMessage(text, "user");
  textarea.value = "";
  button.disabled = true;
  const pending = addMessage("Thinking…", "assistant pending");

  try {
    const response = await fetch("/api/chat/", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": document.querySelector('meta[name="csrf-token"]').content,
      },
      body: JSON.stringify({ message: text }),
    });
    const payload = await response.json();
    pending.textContent = response.ok ? payload.answer : payload.error;
    pending.classList.remove("pending");
  } catch (_error) {
    pending.textContent = "The assistant could not be reached. Please try again.";
    pending.classList.remove("pending");
  } finally {
    button.disabled = false;
    textarea.focus();
  }
});
