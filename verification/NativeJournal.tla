-------------------------- MODULE NativeJournal --------------------------
\* One client path, serialized connect/restore operations and atomic file writes.
\* Each string denotes a distinct file image. "absent" denotes no original file.
VARIABLES original, disk, journal, pending
vars == <<original, disk, journal, pending>>
Images == {"modelA", "modelB"}
NoJournal == [saved |-> "none", previous |-> "none", applied |-> "none"]

Init ==
    /\ original \in {"existing", "absent"}
    /\ disk = original
    /\ journal = NoJournal
    /\ pending = FALSE

Prepare(image) ==
    /\ ~pending
    /\ IF journal = NoJournal THEN TRUE ELSE disk = journal.applied
    /\ journal' = [saved |-> IF journal = NoJournal THEN disk ELSE journal.saved,
                   previous |-> disk, applied |-> image]
    /\ pending' = TRUE
    /\ UNCHANGED <<disk, original>>

FinishWrite ==
    /\ pending
    /\ disk' = journal.applied
    /\ pending' = FALSE
    /\ UNCHANGED <<journal, original>>

InterruptWrite ==
    /\ pending
    /\ pending' = FALSE
    /\ UNCHANGED <<disk, journal, original>>

EditBetweenOperations ==
    /\ ~pending /\ journal # NoJournal
    /\ disk' = "external edit"
    /\ UNCHANGED <<journal, pending, original>>

Restore ==
    /\ ~pending /\ journal # NoJournal
    /\ disk \in {journal.applied, journal.previous}
    /\ disk' = journal.saved
    /\ journal' = NoJournal
    /\ UNCHANGED <<pending, original>>

Next == (\E image \in Images : Prepare(image))
        \/ FinishWrite \/ InterruptWrite \/ EditBetweenOperations \/ Restore
Spec == Init /\ [][Next]_vars

OriginalPreserved == IF journal = NoJournal THEN disk = original ELSE journal.saved = original
Recoverable == (~pending /\ journal # NoJournal /\ disk # "external edit") => ENABLED Restore
ProtectExternalEdit == [][disk = "external edit" => UNCHANGED <<disk, journal>>]_vars
=============================================================================
