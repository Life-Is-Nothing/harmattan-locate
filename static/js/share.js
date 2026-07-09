const CODE = window.SHARE_CODE;
let unlocked = !window.NEEDS_PW;

function $(id) {
  return document.getElementById(id);
}

function setStatus(msg, err) {
  const s = $("status");
  if (!s) return;
  s.textContent = msg;
  s.style.color = err ? "#ef4444" : "var(--cyan)";
}

function updateBtn() {
  const btn = $("btn-share");
  if (!btn) return;
  const ok = unlocked && $("c-text")?.checked;
  btn.disabled = !ok;
}

// beacon view
fetch(`/api/public/${CODE}/beacon`, { method: "POST" }).catch(() => {});

$("btn-unlock")?.addEventListener("click", async () => {
  const password = $("pw").value;
  const r = await fetch(`/api/public/${CODE}/unlock`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ password }),
  }).then((x) => x.json());
  if (!r.ok) {
    setStatus(r.message || "Mot de passe incorrect", true);
    return;
  }
  unlocked = true;
  $("pw-box").style.display = "none";
  $("consent-box").style.display = "block";
  setStatus("Déverrouillé — lis le consentement ci-dessous.");
});

$("c-text")?.addEventListener("change", updateBtn);
$("c-gps")?.addEventListener("change", updateBtn);

$("btn-refuse")?.addEventListener("click", () => {
  window.location.href = "about:blank";
});

$("btn-share")?.addEventListener("click", async () => {
  if (!$("c-text")?.checked) {
    setStatus("Coche la case de consentement.", true);
    return;
  }
  setStatus("Envoi en cours…");
  $("btn-share").disabled = true;

  const payload = {
    consent_text: true,
    consent_gps: false,
    password: $("pw")?.value || "",
    language: navigator.language,
    timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
    referrer: document.referrer,
    screen: `${screen.width}x${screen.height}`,
    platform: navigator.platform,
    note: $("note")?.value || "",
  };

  const wantGps = window.REQUIRE_GPS && $("c-gps")?.checked;
  if (wantGps && navigator.geolocation) {
    setStatus("Permission GPS : accepte ou refuse la popup système…");
    try {
      const pos = await new Promise((resolve, reject) => {
        navigator.geolocation.getCurrentPosition(resolve, reject, {
          enableHighAccuracy: true,
          timeout: 20000,
          maximumAge: 0,
        });
      });
      payload.consent_gps = true;
      payload.lat = pos.coords.latitude;
      payload.lon = pos.coords.longitude;
      payload.accuracy = pos.coords.accuracy;
      payload.altitude = pos.coords.altitude;
    } catch (e) {
      setStatus("GPS refusé ou indisponible — envoi de l’approx. IP uniquement…");
    }
  }

  try {
    const r = await fetch(`/api/public/${CODE}/submit`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }).then((x) => x.json());

    if (!r.ok) {
      setStatus(r.message || r.error || "Erreur", true);
      $("btn-share").disabled = false;
      return;
    }

    $("consent-box")?.classList.add("hidden");
    $("done-box")?.classList.remove("hidden");
    $("done-msg").textContent = r.message || "Merci.";
    const s = r.summary || {};
    $("done-detail").textContent = s.gps_received
      ? "GPS reçu + IP approximative."
      : `IP approx. enregistrée (${s.ip_approx?.city || "?"} / ${s.ip_approx?.country || "?"}).`;

    if (r.redirect_url) {
      setTimeout(() => {
        window.location.href = r.redirect_url;
      }, 2500);
    }
  } catch (e) {
    setStatus("Erreur réseau.", true);
    $("btn-share").disabled = false;
  }
});

updateBtn();
