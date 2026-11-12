document.addEventListener('DOMContentLoaded', () => {
  const pills = document.querySelectorAll('.login-demo-pill');
  const emailInput = document.getElementById('email');
  const passInput = document.getElementById('password');

  pills.forEach((btn) => {
    btn.addEventListener('click', () => {
      const email = btn.getAttribute('data-demo-email');
      const pass = btn.getAttribute('data-demo-pass');
      if (emailInput && passInput && email && pass) {
        emailInput.value = email;
        passInput.value = pass;
        emailInput.dispatchEvent(new Event('input', { bubbles: true }));
        passInput.dispatchEvent(new Event('input', { bubbles: true }));
        passInput.focus();
      }
    });
  });
});
