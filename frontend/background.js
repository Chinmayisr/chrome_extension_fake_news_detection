chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === "open_chatbot") {
    chrome.windows.create({
      url: chrome.runtime.getURL("chatbot.html"),
      type: "popup",
      width: 400,
      height: 600
    });
  }
});
