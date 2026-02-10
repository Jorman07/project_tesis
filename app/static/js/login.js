document.getElementById('loginForm').addEventListener('submit', async (e) => {
  e.preventDefault();

  const cedula = document.getElementById('username').value;
  const password = document.getElementById('password').value;
  const errorBox = document.getElementById('loginError');

  errorBox.textContent = '';

  try {
    const res = await fetch('/auth/login', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        cedula: cedula,
        password: password
      })
    });

    const data = await res.json();

    if (!res.ok) {
      errorBox.textContent = data.message || 'Error al iniciar sesión';
      return;
    }

    // Login exitoso
    window.location.href = data.redirect;

  } catch (err) {
    console.error(err);
    errorBox.textContent = 'Error de conexión con el servidor';
  }
});
