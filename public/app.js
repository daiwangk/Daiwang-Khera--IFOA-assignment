const startBtn = document.getElementById("start-btn");
const submitBtn = document.getElementById("submit-btn");
const nextBtn = document.getElementById("next-btn");
const answerForm = document.getElementById("answer-form");
const optionsContainer = document.getElementById("options-container");
const questionText = document.getElementById("question-text");
const questionCount = document.getElementById("question-count");
const levelBadge = document.getElementById("level-badge");
const topicBadge = document.getElementById("topic-badge");
const feedbackBox = document.getElementById("feedback");
const finalResult = document.getElementById("final-result");

let finished = false;
let currentLevel = 1;
let questionCountState = 1;
let correctCountState = 0;
let currentQuestionState = null;
let stateToken = "";
let canLoadNextQuestion = false;
let pendingLastResult = null;

function setMeta(questionNumber, maxQuestions, level, topic) {
  questionCount.textContent = `Question ${questionNumber}/${maxQuestions}`;
  levelBadge.textContent = `Level ${level}/10`;
  topicBadge.textContent = `Topic ${topic || "-"}`;
}

function setLoadingState(isLoading) {
  submitBtn.disabled = isLoading || !currentQuestionState || finished || canLoadNextQuestion;
  nextBtn.disabled = isLoading || !canLoadNextQuestion || finished;
  startBtn.disabled = isLoading || !!currentQuestionState;
}

function showFeedback(correct, feedback, explanation) {
  feedbackBox.classList.remove("hidden", "correct", "incorrect");
  feedbackBox.classList.add(correct ? "correct" : "incorrect");
  const statusClass = correct ? "correct" : "incorrect";
  const statusText = correct ? "Correct" : "Incorrect";

  feedbackBox.innerHTML = `
    <strong class="${statusClass}">${statusText}</strong>
    <p>${feedback}</p>
    <p><strong>Reference:</strong> ${explanation || "No explanation provided."}</p>
  `;
}

function showError(message) {
  feedbackBox.classList.remove("hidden");
  feedbackBox.classList.add("incorrect");
  feedbackBox.innerHTML = `<strong class="incorrect">Error</strong><p>${message}</p>`;
}

function renderOptions(options) {
  const letters = ["A", "B", "C", "D"];
  optionsContainer.innerHTML = options
    .map((opt, i) => {
      const letter = letters[i];
      const id = `option-${letter}`;
      return `
        <label class="option-item" for="${id}">
          <input type="radio" id="${id}" name="mcq-option" value="${letter}" />
          <span><strong>${letter}.</strong> ${opt}</span>
        </label>
      `;
    })
    .join("");
}

function getSelectedOption() {
  const selected = document.querySelector('input[name="mcq-option"]:checked');
  return selected ? selected.value : "";
}

async function parseJsonResponse(res) {
  let data = null;
  try {
    data = await res.json();
  } catch {
    data = null;
  }

  if (!res.ok) {
    throw new Error(data?.error || data?.detail || "Network error. Please try again.");
  }

  return data;
}

function resetLocalState() {
  finished = false;
  currentLevel = 1;
  questionCountState = 1;
  correctCountState = 0;
  currentQuestionState = null;
  stateToken = "";
  canLoadNextQuestion = false;
  pendingLastResult = null;
  optionsContainer.innerHTML = "";
  nextBtn.classList.add("hidden");
  nextBtn.disabled = true;
}

async function loadNextQuestion() {
  if (!canLoadNextQuestion || !pendingLastResult) {
    return;
  }

  setLoadingState(true);

  try {
    const nextRes = await fetch("/api/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        stateToken,
        lastResult: { correct: pendingLastResult.correct }
      })
    });
    const nextData = await parseJsonResponse(nextRes);

    if (nextData.status === "complete") {
      finished = true;
      currentQuestionState = null;
      canLoadNextQuestion = false;
      pendingLastResult = null;
      nextBtn.classList.add("hidden");
      questionText.textContent = "Quiz completed.";
      finalResult.classList.remove("hidden");
      finalResult.innerHTML = `
        <h3>Final Result</h3>
        <p>Final Level: ${nextData.final_level}/10</p>
        <p>Total Correct: ${nextData.correct_count}/10</p>
        <p>${nextData.message}</p>
      `;
      startBtn.disabled = false;
      return;
    }

    currentQuestionState = {
      question: nextData.question,
      options: nextData.options,
      correctOption: nextData.correctOption,
      explanation: nextData.explanation,
      topic: nextData.topic
    };
    stateToken = nextData.stateToken || "";
    canLoadNextQuestion = false;
    pendingLastResult = null;

    feedbackBox.classList.add("hidden");
    nextBtn.classList.add("hidden");

    setMeta(
      nextData.questionNumber,
      nextData.maxQuestions,
      nextData.level,
      nextData.topic
    );
    questionText.textContent = nextData.question;
    renderOptions(nextData.options || []);
  } catch {
    showError("Network error. Please try again.");
  } finally {
    setLoadingState(false);
  }
}

startBtn.addEventListener("click", async () => {
  resetLocalState();
  setLoadingState(true);
  finalResult.classList.add("hidden");
  feedbackBox.classList.add("hidden");

  try {
    const res = await fetch("/api/start", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        currentLevel,
        questionCount: questionCountState
      })
    });
    const data = await parseJsonResponse(res);

    currentQuestionState = {
      question: data.question,
      options: data.options,
      correctOption: data.correctOption,
      explanation: data.explanation,
      topic: data.topic
    };
    stateToken = data.stateToken || "";

    setMeta(data.questionNumber, data.maxQuestions, data.level, data.topic);
    questionText.textContent = data.question;
    renderOptions(data.options || []);
    canLoadNextQuestion = false;
    pendingLastResult = null;
    nextBtn.classList.add("hidden");
    submitBtn.disabled = false;
  } catch {
    showError("Network error. Please try again.");
  } finally {
    setLoadingState(false);
  }
});

answerForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!currentQuestionState || finished) {
    return;
  }

  const answer = getSelectedOption();
  if (!answer) {
    showError("Please select an option before submitting.");
    return;
  }

  setLoadingState(true);

  try {
    const res = await fetch("/api/submit", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        stateToken,
        answer,
        currentLevel,
        questionCount: questionCountState,
        correctCount: correctCountState,
        currentQuestion: currentQuestionState
      })
    });

    const data = await parseJsonResponse(res);

    showFeedback(data.correct, data.feedback, data.explanation);
    currentLevel = data.nextLevel;
    correctCountState = data.updatedCorrectCount ?? correctCountState;

    if (data.finished) {
      finished = true;
      currentQuestionState = null;
      canLoadNextQuestion = false;
      pendingLastResult = null;
      submitBtn.disabled = true;
      nextBtn.classList.add("hidden");
      questionText.textContent = "Quiz completed.";
      finalResult.classList.remove("hidden");
      finalResult.innerHTML = `
        <h3>Final Result</h3>
        <p>${data.summary}</p>
        <p>Total Correct: ${data.totalCorrect}/${data.totalQuestions}</p>
      `;
      startBtn.disabled = false;
      return;
    }

    questionCountState = data.nextQuestionCount;
    stateToken = data.stateToken || "";
    canLoadNextQuestion = true;
    pendingLastResult = { correct: data.correct };
    nextBtn.classList.remove("hidden");
  } catch {
    showError("Network error. Please try again.");
  } finally {
    setLoadingState(false);
  }
});

nextBtn.addEventListener("click", async () => {
  await loadNextQuestion();
});
