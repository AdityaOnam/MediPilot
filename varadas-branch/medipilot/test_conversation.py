from intake.pipeline import IntakePipeline
from intake.llm_structurer import GroqLLMStructurer
from intake.models import AgeInfo, AgeSource, AgeStatus


pipeline = IntakePipeline(
    patient_id="test-001",
    structurer=GroqLLMStructurer()
)


while not pipeline.complete:

    print("\nMediPilot:", pipeline.current_prompt)

    answer = input("You: ")

    # Age is handled separately by the current architecture.
    if pipeline.session.state.value == "AGE_CONTEXT":
        try:
            age = int(answer)

            pipeline.record_age(
                AgeInfo(
                    value_days=age * 365,
                    source=AgeSource.PATIENT,
                    status=AgeStatus.KNOWN
                )
            )
        except ValueError:
            print("Please enter age as a number.")
        continue

    try:
        pipeline.answer_text(answer)

    except Exception as e:
        print("Invalid answer:", e)


# The loop above exits as soon as pipeline.complete becomes True, which can
# happen the same turn a terminal state (human assistance requested, or an
# early stop on a confirmed red flag) is reached -- so the acknowledgment
# for that state is shown here, once, rather than never.
if pipeline.current_prompt:
    print("\nMediPilot:", pipeline.current_prompt)

print("\n=== INTAKE COMPLETE ===")

outcome = pipeline.finalize()

print("\nStructured narrative:")
print(outcome.record.narrative)

print("\nRed flag result:")
print(outcome.red_flag)

print("\nState history:")
print(outcome.record.state_history)