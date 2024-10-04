  const moodResults = {{ mood_results | tojson }};
  const moodList = document.getElementById("mood-list");
  moodList.innerHTML = ""; 

  for (const [mood, percentage] of Object.entries(moodResults)) {
    const progressContainer = document.createElement("div");
    progressContainer.classList.add("progress-container");

    const circularProgress = document.createElement("div");
    circularProgress.classList.add("circular-progress");
    circularProgress.style.setProperty("--percentage", percentage);

    const progressValue = document.createElement("div");
    progressValue.classList.add("progress-value");
    progressValue.innerText = `${percentage.toFixed(2)}%`;

    const moodLabel = document.createElement("div");
    moodLabel.classList.add("mood-label");
    moodLabel.innerText = mood;

    progressContainer.appendChild(circularProgress);
    progressContainer.appendChild(progressValue);
    progressContainer.appendChild(moodLabel);
    moodList.appendChild(progressContainer);

    circularProgress.offsetWidth; 
    circularProgress.classList.add("animate"); 
  }
});