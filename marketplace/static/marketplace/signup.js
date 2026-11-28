const signupForm = document.querySelector("[data-signup-form]");
const steps = [...signupForm.querySelectorAll("[data-signup-step]")];
const progress = signupForm.querySelector("[data-signup-progress]");
const count = progress.querySelector("[data-signup-count]");
const back = signupForm.querySelector("[data-signup-back]");
const next = signupForm.querySelector("[data-signup-next]");
let currentStep = 0;

function showStep(index, focusHeading = true) {
  currentStep = index;
  steps.forEach((step, position) => {
    step.hidden = position !== currentStep;
  });
  count.textContent = `Step ${currentStep + 1} of ${steps.length}`;
  progress.querySelector("progress").value = currentStep + 1;
  back.hidden = currentStep === 0;
  next.textContent = currentStep === steps.length - 1 ? "Create account" : "Continue";
  if (focusHeading) {
    steps[currentStep].querySelector("legend").focus();
  }
}

back.addEventListener("click", () => showStep(currentStep - 1));

signupForm.addEventListener("submit", (event) => {
  const lastStep = currentStep === steps.length - 1;
  const stepsToValidate = lastStep ? steps : [steps[currentStep]];
  for (const step of stepsToValidate) {
    const invalidInput = [...step.elements].find((input) => input.willValidate && !input.validity.valid);
    if (invalidInput) {
      event.preventDefault();
      showStep(steps.indexOf(step), false);
      invalidInput.reportValidity();
      return;
    }
  }
  if (!lastStep) {
    event.preventDefault();
    showStep(currentStep + 1);
  }
});

signupForm.noValidate = true;
progress.hidden = false;
const firstError = steps.findIndex((step) => step.querySelector(".errorlist"));
showStep(Math.max(0, firstError), firstError >= 0);
