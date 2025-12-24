from django.shortcuts import render
from django.http import JsonResponse
from .models import StudentInteractionSession, Message, GeneratedAssignment, Student
from .ai_utils import (
    call_model,
    build_session_context,
    evaluate_skill_mastery,
    build_conversation_history,
    should_include_context,
    get_recent_conversation_excerpt
)
from .serializers import AssignmentRequirementSerializer
from django.views.decorators.csrf import csrf_exempt
import json


def chat_page(request):
    return render(request, 'chat.html')


@csrf_exempt
def student_response(request, session_id):
    """
    Handle student message and generate AI response.

    CRITICAL: We send the FULL conversation history to the AI so it can:
    - Remember what questions it asked
    - Understand the context of student responses
    - Provide coherent follow-ups
    - Track whether student is on/off topic
    """
    session = StudentInteractionSession.objects.get(pk=session_id)
    student_message = request.POST.get('message', '').strip()

    current_phase = session.session_data.get("current_phase", "intro")

    # ========================================================================
    # EVIDENCE TRACKING (for evaluation, not for AI context)
    # ========================================================================
    # We track raw evidence separately for the mastery evaluation function
    # This is NOT sent to the AI in the conversation - the AI sees the full
    # conversation history which includes the questions that prompted these responses

    if current_phase == "source_loop" and student_message:
        source_index = session.session_data.get("source_index", 0)
        skill_index = session.session_data.get("skill_index", 0)
        key = f"{source_index}_{skill_index}"

        session_data = session.session_data
        session_data.setdefault("skill_evidence", {})
        session_data["skill_evidence"].setdefault(key, [])
        session_data["skill_evidence"][key].append(student_message)

        session.session_data = session_data
        session.save()

    # ========================================================================
    # BUILD FULL CONVERSATION HISTORY
    # ========================================================================
    # Key change: We use current_skill_only=False to get FULL history
    # The AI needs to see the entire conversation to understand context

    history = build_conversation_history(session, limit_to_current_skill=True)

    # Add the student's current message to history
    history.append({
        "role": "user",
        "content": student_message
    })

    # ========================================================================
    # BUILD SESSION CONTEXT (goes in system prompt)
    # ========================================================================
    # This tells the AI WHERE we are (phase, source, skill) but not WHAT to say
    # The AI uses this + conversation history + reference materials to respond

    session_context = build_session_context(session, is_phase_transition=False)

    # Determine if historical context should be included based on current skill
    include_context = True
    # ========================================================================
    # GET AI RESPONSE
    # ========================================================================
    # The AI now has:
    # 1. System prompt with role and behavior rules
    # 2. Skill definitions (if include_skills=True)
    # 3. Historical context (if include_context=True)
    # 4. Current session state (phase, source, skill)
    # 5. FULL conversation history

    ai_response = call_model(
        messages_history=history,
        include_skills=True,
        include_context=include_context,
        session_context=session_context
    )

    if current_phase == "source_loop":
        if "?" in ai_response:
            session_data = session.session_data
            session_data["questions_asked_this_skill"] = session_data.get(
                "questions_asked_this_skill", 0
            ) + 1
            session.session_data = session_data
            session.save()

    # ========================================================================
    # SAVE MESSAGE PAIR
    # ========================================================================
    Message.objects.create(
        session=session,
        request={"message": student_message, "phase": current_phase},
        response={"message": ai_response}
    )

    return JsonResponse({"response": ai_response})


@csrf_exempt
def start_session(request, assignment_id):
    """
    Initialize a new student session and generate welcome message.
    """
    student = Student.objects.get(pk=2)  # TODO: Replace with actual auth
    assignment = GeneratedAssignment.objects.get(pk=assignment_id)

    # Initialize session with starting state
    session = StudentInteractionSession.objects.create(
        student=student,
        assignment=assignment,
        session_data={
            "current_phase": "intro",
            "source_index": 0,
            "skill_index": 0,
            "skill_evidence": {}
        }
    )

    # Generate intro message
    session_context = build_session_context(session, is_phase_transition=False)

    ai_intro = call_model(
        messages_history=[],  # Empty history - this is the first message
        include_skills=False,  # Don't need skill definitions for intro
        include_context=False,  # Don't need historical context for intro
        session_context=session_context
    )

    # Save first AI message
    Message.objects.create(
        session=session,
        request={"message": None, "phase": "intro"},
        response={"message": ai_intro}
    )

    return JsonResponse({
        "session_id": session.session_id,
        "ai_message": ai_intro,
        "sources": assignment.sources,
        "total_skills": len(assignment.requirement.skills_to_target),
        "student_name": student.user.name,
        "teacher_name": assignment.requirement.teacher.user.name,
        "topic": assignment.requirement.topic,
        "guiding_question": assignment.requirement.guiding_question
    })


@csrf_exempt
def advance_phase(request, session_id):
    """
    Handle phase transitions (intro -> source_loop -> next skill -> next source -> complete).

    This is called when student clicks "Ready to Begin" or "Continue" buttons.
    """
    session = StudentInteractionSession.objects.get(pk=session_id)
    session_data = session.session_data
    current_phase = session_data.get("current_phase", "intro")

    print(f"[DEBUG] advance_phase called - current_phase: {current_phase}")  # DEBUG
    print(f"[DEBUG] About to check if current_phase == 'intro': {current_phase == 'intro'}")  # DEBUG
    print(f"[DEBUG] Type of current_phase: {type(current_phase)}")  # DEBUG
    # ========================================================================
    # INTRO -> SOURCE_LOOP (Start first source/skill)
    # ========================================================================
    if current_phase == "intro":
        print(f"[DEBUG] ENTERED intro block")  # DEBUG

        session_data["current_phase"] = "source_loop"
        session_data["source_index"] = 0
        session_data["skill_index"] = 0
        session.session_data = session_data
        session.save()

        # Build session context
        session_context = build_session_context(session, is_phase_transition=True)

        # Get skills list
        skills = session.assignment.requirement.skills_to_target
        print(f"[DEBUG] Skills: {skills}")  # DEBUG

        include_context = should_include_context(skills[0]) if skills else False

        ai_message = call_model(
            messages_history=[],
            include_skills=True,
            include_context=include_context,
            session_context=session_context
        )

        # Save message
        Message.objects.create(
            session=session,
            request={"message": None, "phase": "source_loop", "source_index": 0, "skill_index": 0},
            response={"message": ai_message}
        )

        # Prepare skill info
        current_skill = skills[0] if skills else "Unknown"
        skill_definitions = {
            "Comprehension": "Establish a literal, accurate understanding of what the source explicitly states.",
            "Contextualization": "Place the source within its historical time, place, and conditions.",
            "Sourcing": "Analyze the author, date, audience, and perspective.",
            "Claim/Evidence": "Make a historical claim about the guiding question using the source, providing textual evidence.",
            "Evaluation": "Assess the usefulness and limitations of the source for answering the guiding question."
        }
        current_skill_description = skill_definitions.get(current_skill, "")

        print(f"[DEBUG] Returning - skill: {current_skill}, desc: {current_skill_description[:50]}")  # DEBUG

        return JsonResponse({
            "next_phase": "source_loop",
            "ai_message": ai_message,
            "source_index": 0,
            "skill_index": 0,
            "current_skill": current_skill,
            "current_skill_description": current_skill_description
        })

    # ========================================================================
    # SOURCE_LOOP -> NEXT SKILL OR SOURCE (Check mastery first)
    # ========================================================================
    elif current_phase == "source_loop":
        skill_index = session_data.get("skill_index", 0)
        source_index = session_data.get("source_index", 0)
        skills = session.assignment.requirement.skills_to_target
        sources = session.assignment.sources

        # ====================================================================
        # MASTERY CHECK - Don't advance unless student has shown understanding
        # ====================================================================
        key = f"{source_index}_{skill_index}"
        evidence = session_data.get("skill_evidence", {}).get(key, [])

        # Get recent conversation for better evaluation context
        conversation_excerpt = get_recent_conversation_excerpt(session, num_exchanges=4)

        mastery_result = evaluate_skill_mastery(
            skill=skills[skill_index],
            proficiency=session.assignment.requirement.student_proficiency,
            evidence=evidence,
            conversation_excerpt=conversation_excerpt
        )

        print(f"[DEBUG] Mastery check - Skill: {skills[skill_index]}, Is mastered: {mastery_result.get('is_mastered')}")  # DEBUG
        print(f"[DEBUG] Evidence count: {len(evidence)}")  # DEBUG

        if not mastery_result.get("is_mastered", False):
            # Block advancement - student needs more practice
            # The AI should provide guidance on what to work on
            history = build_conversation_history(session, limit_to_current_skill=False)
            session_context = build_session_context(session, is_phase_transition=False)

            # Add context about why they're blocked (for AI's understanding only)
            session_context += f"\n\n[INTERNAL NOTE - Don't mention this to student]"
            session_context += f"\nMastery check: Student hasn't fully demonstrated '{skills[skill_index]}' yet."
            session_context += f"\nReasoning: {mastery_result.get('reasoning', '')}"
            session_context += f"\nYour task: Acknowledge their effort, then ask ONE focused question to help them go deeper on this skill."

            # Check if we need historical context
            include_context = True

            ai_followup = call_model(
                messages_history=history,
                include_skills=True,
                include_context=include_context,
                session_context=session_context
            )

            # Save this as a regular message (no special "blocked" indicator to student)
            Message.objects.create(
                session=session,
                request={"message": "[Attempted to advance]", "phase": current_phase},
                response={"message": ai_followup}
            )

            return JsonResponse({
                "blocked": True,
                "ai_message": ai_followup,
                "current_skill": skills[skill_index]
            })

        # ====================================================================
        # ADVANCE TO NEXT SKILL
        # ====================================================================
        prev_skill = skills[skill_index]  # BEFORE increment
        skill_index += 1

        # If finished all skills for this source, move to next source
        if skill_index >= len(skills):
            skill_index = 0
            source_index += 1

        # ====================================================================
        # CHECK IF ALL SOURCES COMPLETE
        # ====================================================================
        if source_index >= len(sources):
            session_data["current_phase"] = "complete"
            session.session_data = session_data
            session.save()

            return JsonResponse({
                "next_phase": "complete",
                "ai_message": "Excellent work! You've completed all the sources and demonstrated strong historical thinking skills.",
                "complete": True
            })

        # ====================================================================
        # UPDATE SESSION AND GENERATE NEXT PROMPT
        # ====================================================================
        session_data["skill_index"] = skill_index
        session_data["source_index"] = source_index
        session_data["questions_asked_this_skill"] = 0
        session.session_data = session_data
        session.save()

        # CRITICAL: Refresh session from DB to ensure we have latest data
        session.refresh_from_db()

        print(f"[DEBUG] After save and refresh - source_index: {source_index}, skill_index: {skill_index}")  # DEBUG
        print(f"[DEBUG] Skills list: {skills}")  # DEBUG
        print(f"[DEBUG] Next skill should be: {skills[skill_index]}")  # DEBUG

        # Generate next prompt - this is a phase transition to new skill/source
        session_context = build_session_context(session, is_phase_transition=True)

        print(f"[DEBUG] Calling AI with empty history for phase transition")  # DEBUG
        print(f"[DEBUG] Current skill from context: {skills[skill_index] if skill_index < len(skills) else 'ERROR'}")  # DEBUG

        # Check if we need historical context for the new skill
        include_context = True

        ai_message = call_model(
            messages_history=[],  # Empty - fresh start for new skill
            include_skills=True,
            include_context=include_context,
            session_context=session_context
        )

        print(f"[DEBUG] AI response (first 100 chars): {ai_message[:100]}")  # DEBUG

        # Save phase transition message with indices
        Message.objects.create(
            session=session,
            request={
                "message": None,
                "phase": "source_loop",
                "source_index": source_index,
                "skill_index": skill_index
            },
            response={"message": ai_message}
        )

        return JsonResponse({
            "next_phase": "source_loop",
            "ai_message": ai_message,
            "source_index": source_index,
            "skill_index": skill_index,
            "total_sources": len(sources),
            "total_skills": len(skills),
            "previous_skill": prev_skill,  # <-- use this for mastery notice
            "current_skill": skills[skill_index] if skill_index < len(skills) else "Unknown"
        })

    else:
        return JsonResponse({
            "next_phase": current_phase,
            "ai_message": "Phase not recognized."
        })


@csrf_exempt
def generate_assignment(request, requirement_id):
    """
    Generate an assignment from requirements using AI.
    This is separate from the student interaction flow.
    """
    from .models import AssignmentRequirement

    requirement = AssignmentRequirement.objects.get(pk=requirement_id)
    serializer = AssignmentRequirementSerializer(requirement)
    requirement_json = serializer.data

    prompt = f"""
Generate a structured historical thinking assignment based on these requirements:

{json.dumps(requirement_json, indent=2)}

Return a JSON object with:
- "title": Assignment title
- "sources": List of 3-5 primary source excerpts (each with: title, author, year, text)
- "skills": List of historical thinking skills to practice
- "instructions": Student-friendly instructions
- "epistemology_note": Brief explanation if required

Make sources age-appropriate for the proficiency level.
Each source should be 150-300 words.
"""

    response = call_model(
        messages_history=[{"role": "user", "content": prompt}],
        include_skills=False,
        include_context=False
    )

    assignment = GeneratedAssignment.objects.create(
        requirement=requirement,
        json_payload={"ai_output": response},
        readable_format=response
    )

    return JsonResponse({
        "assignment_id": assignment.assignment_id,
        "ai_output": response
    })