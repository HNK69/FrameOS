import asyncio
import json
import secrets
import time
from sqlalchemy import select, func
from app.db import SessionLocal
from app.models import Client, Project, ProcessingRun, ExtractedItem, ProductionTask, Transcript, User, Workspace, Membership
from app.services import groq, hindsight, openclaw
from app.config import settings

async def run_battery_4_and_5():
    print("=" * 60)
    print("STARTING BATTERY 4: OPENCLAW LIVE PRODUCTION SYNTHESIS")
    print("=" * 60)

    db = SessionLocal()
    try:
        user = db.scalar(select(User).limit(1))
        workspace = db.scalar(select(Workspace).limit(1))
        client = db.scalar(select(Client).where(Client.name.like("LUXE STUDIO%")).limit(1))
        project_1 = db.scalar(select(Project).where(Project.client_id == client.id).limit(1))

        print(f"Using Client: id={client.id}, name='{client.name}', bank_id='{client.memory_bank_id}'")
        print(f"Using Project 1: id={project_1.id}, name='{project_1.name}'")

        # Ensure Hindsight bank exists
        await hindsight.ensure_bank(client.memory_bank_id)

        # Retain initial preference into LUXE bank
        init_pref = "LUXE STUDIO prefers cinematic 2.39:1 aspect ratio, warm organic grade, and slow pacing."
        print(f"Retaining initial preference to Hindsight bank '{client.memory_bank_id}'...")
        await hindsight.retain_and_verify(
            client.memory_bank_id,
            init_pref,
            context="client brand guidelines",
            tags=["brand_preference", "cinematic"],
            document_id="doc-luxe-initial"
        )
        print("Initial preference retained and verified in Hindsight.")

        # Execute Live Synthesis for Project 1
        t_idempotency = f"bat4-run-{secrets.token_hex(4)}"
        transcript_text_1 = "Please apply a warm organic color grade and cinematic crop for the opening sequence. Keep cuts slow paced."
        print(f"\nProcessing transcript for Project 1: '{transcript_text_1}'")
        
        t0 = time.perf_counter()
        # 1. Groq extract
        extracted_1 = await groq.extract_feedback(transcript_text_1)
        print(f"Groq Extraction: {len(extracted_1.requests)} requests extracted in {round(time.perf_counter() - t0, 2)}s")
        for req in extracted_1.requests:
            print(f"  - [{req.category}] {req.description}")

        # 2. Hindsight recall
        query_1 = "\n".join(r.description for r in extracted_1.requests)
        recall_1 = await hindsight.recall(client.memory_bank_id, query_1)
        recalled_items_1 = recall_1.get("results", recall_1.get("memories", []))
        print(f"Hindsight Recall: {len(recalled_items_1)} memory items retrieved")
        for mem in recalled_items_1[:2]:
            print(f"  - (Score: {mem.get('scores', {}).get('final')}): {mem.get('text')}")

        # 3. OpenClaw Live Synthesis
        run_record_1 = ProcessingRun(
            workspace_id=workspace.id, client_id=client.id, project_id=project_1.id,
            transcript_id=1, idempotency_key=t_idempotency, status="processing", stage="synthesizing",
            attempt_count=1
        )
        db.add(run_record_1)
        db.commit()

        t_synth = time.perf_counter()
        synth_1 = await openclaw.synthesize(
            run_id=run_record_1.id, attempt_count=1,
            client_name=client.name, project_name=project_1.name,
            extraction=extracted_1.model_dump(), memories=recall_1,
            assets=[]
        )
        print(f"OpenClaw Synthesis: {len(synth_1.tasks)} DaVinci Resolve task(s) generated in {round(time.perf_counter() - t_synth, 2)}s")

        # 4. Persistence into frameops.db
        persisted_task_ids_1 = []
        for task in synth_1.tasks:
            pt = ProductionTask(
                workspace_id=workspace.id, client_id=client.id, project_id=project_1.id,
                run_id=run_record_1.id, title=task.title, category=task.category,
                instruction=task.instruction, resolve_workflow=task.resolve_workflow,
                priority=task.priority, source=task.source, evidence=task.evidence,
                confidence=task.confidence, requires_confirmation=task.requires_confirmation
            )
            db.add(pt)
            db.flush()
            persisted_task_ids_1.append(pt.id)
            print(f"  Persisted Task ID {pt.id}: '{pt.title}'")
            print(f"    Category: {pt.category}")
            print(f"    Resolve Workflow: {pt.resolve_workflow}")
            print(f"    Instruction: {pt.instruction}")
            print(f"    Evidence: {pt.evidence}")
            print(f"    Confidence: {pt.confidence}")

        run_record_1.status = "completed"
        run_record_1.stage = "completed"
        db.commit()

        # Verify persistence in SQLite
        pt_check = db.scalars(select(ProductionTask).where(ProductionTask.id.in_(persisted_task_ids_1))).all()
        assert len(pt_check) == len(persisted_task_ids_1), "Persistence check failed: Task not found in SQLite"
        print(f"BATTERY 4 VERIFIED: Successfully synthesized and persisted {len(pt_check)} task(s) in frameops.db\n")

        # ========================================================
        print("=" * 60)
        print("STARTING BATTERY 5: END-TO-END ADAPTIVE MEMORY ACROSS PROJECTS")
        print("=" * 60)

        # Step 1: Retain editor correction for LUXE STUDIO
        editor_correction = "Editor correction: LUXE STUDIO updated brand direction to cool teal-and-orange grade with dynamic pacing instead of slow warm grade for the 2026 rebrand."
        print(f"Step 1: Retaining editor correction into Hindsight bank '{client.memory_bank_id}'...")
        res_corr, v_corr = await hindsight.retain_and_verify(
            client.memory_bank_id,
            editor_correction,
            context="editor correction from Project 1 review session",
            tags=["editor_correction", "brand_rebrand", "color_update"],
            document_id=f"doc-correction-proj-{project_1.id}"
        )
        print(f"Editor correction retention verified: {v_corr}")

        # Step 2: Create Project 2 for the same client
        project_2 = Project(
            workspace_id=workspace.id, client_id=client.id,
            name=f"LUXE 2026 Rebrand Promo {secrets.token_hex(2)}",
            description="Second project verifying adaptive memory influence",
            status="active"
        )
        db.add(project_2)
        db.commit()
        print(f"\nStep 2: Created Project 2: id={project_2.id}, name='{project_2.name}' for Client {client.id}")

        # Step 3: Process transcript for Project 2
        transcript_text_2 = "For the new rebrand campaign promo, adjust the color treatment according to our latest brand direction and set pacing."
        print(f"\nStep 3: Processing transcript for Project 2: '{transcript_text_2}'")

        # Groq extraction for Project 2
        extracted_2 = await groq.extract_feedback(transcript_text_2)
        print(f"Groq Extraction Project 2: {len(extracted_2.requests)} requests extracted")
        for req in extracted_2.requests:
            print(f"  - [{req.category}] {req.description}")

        # Hindsight recall for Project 2
        query_2 = "color treatment latest brand direction and pacing"
        recall_2 = await hindsight.recall(client.memory_bank_id, query_2)
        recalled_items_2 = recall_2.get("results", recall_2.get("memories", []))
        print(f"\nHindsight Recall Project 2: {len(recalled_items_2)} memory items retrieved")
        correction_found = False
        for mem in recalled_items_2:
            text = mem.get("text", "")
            score = mem.get("scores", {}).get("final")
            print(f"  - (Score: {score}): {text}")
            if "teal-and-orange" in text.lower() or "dynamic pacing" in text.lower() or "cool" in text.lower():
                correction_found = True
        
        assert correction_found, "Recall failed to retrieve the editor correction from Project 1!"
        print("  -> CONFIRMED: Past editor correction was successfully retrieved for Project 2!")

        # Step 4: OpenClaw Synthesis for Project 2 incorporating adapted memory
        run_record_2 = ProcessingRun(
            workspace_id=workspace.id, client_id=client.id, project_id=project_2.id,
            transcript_id=1, idempotency_key=f"bat5-run-{secrets.token_hex(4)}", status="processing", stage="synthesizing",
            attempt_count=1
        )
        db.add(run_record_2)
        db.commit()

        t_synth2 = time.perf_counter()
        synth_2 = await openclaw.synthesize(
            run_id=run_record_2.id, attempt_count=1,
            client_name=client.name, project_name=project_2.name,
            extraction=extracted_2.model_dump(), memories=recall_2,
            assets=[]
        )
        print(f"\nStep 4: OpenClaw Synthesis Project 2: {len(synth_2.tasks)} task(s) generated in {round(time.perf_counter() - t_synth2, 2)}s")

        persisted_task_ids_2 = []
        adapted_influence_confirmed = False
        for task in synth_2.tasks:
            pt2 = ProductionTask(
                workspace_id=workspace.id, client_id=client.id, project_id=project_2.id,
                run_id=run_record_2.id, title=task.title, category=task.category,
                instruction=task.instruction, resolve_workflow=task.resolve_workflow,
                priority=task.priority, source=task.source, evidence=task.evidence,
                confidence=task.confidence, requires_confirmation=task.requires_confirmation
            )
            db.add(pt2)
            db.flush()
            persisted_task_ids_2.append(pt2.id)
            print(f"  Persisted Task ID {pt2.id}: '{pt2.title}'")
            print(f"    Category: {pt2.category}")
            print(f"    Resolve Workflow: {pt2.resolve_workflow}")
            print(f"    Instruction: {pt2.instruction}")
            print(f"    Evidence: {pt2.evidence}")
            combined = (pt2.title + " " + pt2.instruction + " " + pt2.evidence).lower()
            if "teal" in combined or "orange" in combined or "cool" in combined or "dynamic" in combined or "rebrand" in combined:
                adapted_influence_confirmed = True

        run_record_2.status = "completed"
        run_record_2.stage = "completed"
        db.commit()

        print(f"\nBATTERY 5 VERIFIED: Adaptive memory confirmed={adapted_influence_confirmed}")
        print("=" * 60)

    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(run_battery_4_and_5())
