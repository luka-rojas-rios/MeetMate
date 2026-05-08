document.addEventListener("DOMContentLoaded", () => {
  const passwordButtons = document.querySelectorAll(".password-toggle");

  passwordButtons.forEach((button) => {
    button.addEventListener("click", () => {
      const targetId = button.dataset.target;
      const input = document.getElementById(targetId);

      if (!input) return;

      input.type = input.type === "password" ? "text" : "password";
    });
  });

  const photoInput = document.getElementById("profile_photo");
  const photoPreview = document.getElementById("photoPreview");

  if (photoInput && photoPreview) {
    photoInput.addEventListener("change", () => {
      const file = photoInput.files[0];

      if (!file) return;

      const reader = new FileReader();

      reader.onload = (event) => {
        photoPreview.src = event.target.result;
      };

      reader.readAsDataURL(file);
    });
  }

  const confirmForms = document.querySelectorAll(".confirm-form");

  confirmForms.forEach((form) => {
    form.addEventListener("submit", (event) => {
      const confirmed = confirm("¿Seguro que quieres eliminar este elemento?");

      if (!confirmed) {
        event.preventDefault();
      }
    });
  });
});