(function () {
  // --- CONFIGURATION ---
  const BACKEND_URL = "http://localhost:8000/analyze_news/";

  // Floating icon
  const button = document.createElement("div");
  button.id = "fake-news-icon";
  button.title = "Check news credibility";
  button.innerHTML = "🕵️‍♂️";

  // Popup
  const popup = document.createElement("div");
  popup.id = "fake-news-popup";
  popup.style.display = "none";

  // Only set up the popup HTML with loading or backend result, not dummy data
  popup.innerHTML = `
    <h2>🕵️‍♂️ Fake News Detection</h2>
    <span>Click the button to check news authenticity.</span>
    <button id="open-chatbot">Chat with Verifier</button>
    <button id="close-popup">Close</button>
  `;

  // Append icon and popup to the body
  document.body.appendChild(button);
  document.body.appendChild(popup);

  // Style the floating icon
  Object.assign(button.style, {
    position: "fixed",
    bottom: "20px",
    right: "20px",
    zIndex: "1000",
    fontSize: "30px",
    cursor: "pointer",
    borderRadius: "50%",
    backgroundColor: "#f0f0f0",
    padding: "10px"
  });

  // Style the popup
  Object.assign(popup.style, {
    position: "fixed",
    bottom: "80px",
    right: "20px",
    zIndex: "1000",
    width: "300px",
    padding: "20px",
    backgroundColor: "#fff",
    border: "1px solid #ccc",
    boxShadow: "0px 4px 6px rgba(0,0,0,0.1)",
    borderRadius: "10px"
  });

  // --- UI Helper ---
  function showDetectionResult(result, isLoading = false) {
    let resultDiv = document.getElementById("fake-news-extension-panel");
    if (!resultDiv) {
      resultDiv = document.createElement("div");
      resultDiv.id = "fake-news-extension-panel";
      resultDiv.style.position = "fixed";
      resultDiv.style.bottom = "0";
      resultDiv.style.right = "0";
      resultDiv.style.zIndex = "99999";
      resultDiv.style.background = "#fff";
      resultDiv.style.border = "2px solid #333";
      resultDiv.style.borderRadius = "8px 8px 0 0";
      resultDiv.style.padding = "16px";
      resultDiv.style.boxShadow = "0 -2px 12px rgba(0,0,0,0.2)";
      resultDiv.style.fontFamily = "Arial, sans-serif";
      resultDiv.style.maxWidth = "350px";
      resultDiv.style.minWidth = "250px";
      resultDiv.style.color = "#222";
      resultDiv.style.transition = "transform 0.3s";
      document.body.appendChild(resultDiv);
    }
    // Always clear the panel and show only loading if isLoading is true
    if (isLoading) {
      resultDiv.innerHTML = `<div style="display:flex;flex-direction:column;align-items:center;justify-content:center;height:100px;">
        <span style="font-size:2em;">⏳</span>
        <b style="margin-top:10px;">Loading verdict...</b>
      </div>`;
      return;
    }
    const trustedNewsValue = (typeof result.trusted_news === "string" && result.trusted_news.trim() !== "")
      ? result.trusted_news
      : (result.trusted_news === null || result.trusted_news === undefined)
        ? "N/A"
        : String(result.trusted_news);
    resultDiv.innerHTML = `
        <b>📰 Fake News Detection Result</b><br><br>
        <b>Trust Score:</b> ${typeof result.trust_score === "number" ? result.trust_score.toFixed(2) : result.trust_score}<br>
        <b>Verdict:</b> ${result.verdict || (result.is_fake === false ? "Trustworthy" : result.is_fake === true ? "Fake" : "Unknown")}<br>
        ${result.correct_information ? `<b>Correct Info:</b> <span style="font-size:0.95em">${result.correct_information}</span><br>` : ""}
        <b>Trusted News:</b> <span style="font-size:0.95em">${trustedNewsValue}</span><br>
        <button id="close-fake-news-extension-panel" style="margin-top:10px;padding:4px 10px;">Close</button>
    `;
    document.getElementById("close-fake-news-extension-panel").onclick = () => {
      resultDiv.style.transform = "translateY(100%)";
      setTimeout(() => resultDiv.remove(), 300);
    };
  }

  // --- Backend Communication ---
  async function checkNewsAuthenticity(newsText) {
    try {
      const response = await fetch(BACKEND_URL, {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({ text: newsText })
      });

      if (!response.ok) {
        throw new Error("Network response was not ok");
      }

      const result = await response.json();
      showDetectionResult(result);
    } catch (error) {
      alert("Error checking news authenticity: " + error.message);
    }
  }

  // Scraping logic
  function extractNews() {
    // Select all divs on the page
    const divs = Array.from(document.querySelectorAll("div"));
    let headlines = [];
    let paragraphs = [];

    divs.forEach(div => {
      // Find all matching elements inside this div
      const found = div.querySelectorAll("h1, .main-headline, h1.headline, h1.title, p");
      found.forEach(el => {
        // Classify as headline or paragraph
        if (
          el.matches("h1") ||
          el.matches(".main-headline") ||
          el.matches("h1.headline") ||
          el.matches("h1.title")
        ) {
          headlines.push(el.innerText.trim());
        } else if (el.matches("p")) {
          paragraphs.push(el.innerText.trim());
        }
      });
    });

    // Remove duplicates and empty strings
    headlines = [...new Set(headlines)].filter(Boolean);
    paragraphs = [...new Set(paragraphs)].filter(Boolean);

    return {
      headlines,
      paragraphs
    };
  }
  
  // Send to FastAPI backend and show result in popup
  function sendToBackend(data) {
    showDetectionResult({}, true); // Show loading verdict immediately
    const fullText = `📰 Headline:\n${data.headline}\n\n📄 Description:\n${data.description}`;
    fetch("http://127.0.0.1:8000/run_rag_pipeline/", {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({ text: fullText })
    })
      .then(res => res.json())
      .then(result => {
        showDetectionResult(result); // Show the backend verdict/result in the extension panel
      })
      .catch(err => {
        console.error("❌ Failed to send data:", err);
        alert("Error checking news authenticity: " + err.message);
      });
  }

  // When button is clicked
  button.addEventListener("click", () => {
    // Hide the popup and show only the loading panel
    popup.style.display = "none";
    showDetectionResult({}, true); // Show loading verdict immediately
    const data = extractNews();
    sendToBackend({
      headline: data.headlines.join(" | "),
      description: data.paragraphs.join(" ")
    });
  });

  // Hide popup when clicked outside
  document.addEventListener("click", (e) => {
    if (!popup.contains(e.target) && e.target !== button) {
      popup.style.display = "none";
    }
  });

  // Set popup button listeners
  setTimeout(() => {
    document.getElementById("close-popup").onclick = () => {
      popup.style.display = "none";
    };

    document.getElementById("open-chatbot").onclick = () => {
      chrome.runtime.sendMessage({ type: "open_chatbot" });
    };
  }, 500);

  // --- Example Trigger: Right-click context menu or selection ---
  document.addEventListener("mouseup", function () {
    const selection = window.getSelection().toString().trim();
    if (selection.length > 20) { // Only trigger for reasonably long selections
        if (confirm("Check this news for authenticity?")) {
            checkNewsAuthenticity(selection);
        }
    }
  });

  // --- Optional: Expose function for manual use ---
  // window.checkNewsAuthenticity = checkNewsAuthenticity;
})();
