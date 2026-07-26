(function () {
  const PROD_API_BASE = "https://packin-backend.onrender.com";
  const isLocal = ["localhost", "127.0.0.1"].includes(window.location.hostname);
  window.PACKIN_API_BASE = isLocal ? "http://localhost:8000" : PROD_API_BASE;
})();