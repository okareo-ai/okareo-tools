# Outbound simulations: the agent calls Okareo

Most voice agents answer the phone, so Okareo dials them. An agent that
*places* calls — collections, reminders, sales, callbacks — cannot be
dialed. For those, the direction is reversed: Okareo gives you a phone
number, the agent calls it, and a simulated person answers.

"Outbound" here means **the agent is the one dialing**. It is not about who
speaks first; that is a separate setting on any call.

## How it differs from a normal voice simulation

| | Okareo dials the agent | The agent dials Okareo |
| --- | --- | --- |
| Target | A number, SIP address or room to reach | A receiving target: nothing to dial |
| Start | `run_simulation` | `start_outbound_simulation` |
| When calls happen | Okareo places them at once | Whenever the agent calls the number |
| End | When the calls finish | When you turn it off, or it times out |
| Results | The same tools, once it is off | |

`run_simulation` refuses a receiving target and points here.

## The flow

1. **Register a receiving target** with `create_or_update_target`. It needs
   no number and no carrier. Two optional settings: the caller numbers the
   agent will dial *from* (calls from any other number are not answered),
   and how many calls may be answered at once.
2. **Build the person who answers** with `create_or_update_driver`, and the
   scenario rows with `save_scenario`. Each call the agent places takes
   the next row; after the last row it starts again from the first.
3. **Start** with `start_outbound_simulation`. Pass a completion check, as
   for any voice run; without one the calls are recorded but not judged.
   A turn cap here limits the *answering* side of each call. The reply
   gives the **number to call**, when it will turn itself off, and the id
   to use from here on.
4. **Have the agent call the number.** This is the user's step: trigger a
   campaign, a reminder job, a test dial. Nothing in Okareo places it.
5. **Watch** with `get_outbound_simulation`: it reports whether the line is
   on and how many calls have been answered.
   `list_outbound_simulations` shows every one that is on.
6. **Stop** with `stop_outbound_simulation` as soon as the agent has made
   its calls. It is safe to stop while a call is still in progress: no new
   calls are answered, calls already connected finish, and then the run is
   scored. So stop once the count of calls received reaches what you
   expected; there is no need to wait for the last call to end.
7. **Read the results** with `get_test_run_results` and
   `get_conversation_transcript`, as for any voice run.

## Running it again

An outbound simulation is not re-run; a new one is started. There is no
need to rebuild the call by hand: read the finished run with
`get_test_run_results`, and its rerun block is the
`start_outbound_simulation` call with the same target, scenario, driver,
checks and limits already filled in. Give the new one a name and start it.

Two things change every time: the **run id**, and the **number**. The new
simulation is assigned its own number, which may not be the one used
before, so always give the agent the number the new start returns.
`run_simulation` cannot repeat an outbound simulation and says so.

## Turn it off when you are done

While an outbound simulation is on, it holds one of a limited set of shared
Okareo numbers, and an organization can only have a handful on at once.

- Stop it as soon as the calls are made. Do not leave one on "in case".
- It also turns itself off after a maximum time, or after a stretch with
  no calls. Both are options on `start_outbound_simulation` (a maximum
  duration and an idle timeout, in seconds). The defaults are hours and
  half an hour, so for a quick test set them to minutes.
- If a start is refused because no number is free or too many are already
  on, find the ones that are on with `list_outbound_simulations` and stop
  what is no longer needed. Do not retry in a loop.

## When the real dialer is not available: a stand-in

To try the flow before the user's agent can dial, a second, ordinary
simulation can play the agent: register a normal phone target whose number
to call is the one the outbound simulation was assigned, and run
`run_simulation` against it. That is the one case where `run_simulation`
belongs in this flow — it is aimed at the *phone* target, never at the
receiving target.

Keep the roles straight, because they invert on the dialing run:

| | Answering side (the outbound simulation) | Dialing side (the stand-in) |
| --- | --- | --- |
| Its driver plays | The person being called | The agent that places the call |
| Its "target" is | The receiving target | The phone target pointing at the assigned number |
| "Target speaks first" means | Not applicable; set who speaks first when starting | The person being called speaks first |

Use one scenario row that fits both sides, give the dialing run its own
turn cap, and confirm the call with the user as for any phone run. Say in
the report that a stand-in was used: it proves the Okareo side of the flow,
not the user's dialer.

## Who speaks first

By default the simulated person speaks first, as someone answering a phone
does ("Hello?"). If the agent's dialer expects to speak first on answer,
set that when starting.

## When no calls arrive

A simulation turned off with no calls fails, and says no calls were
received. Before blaming the agent, check, in order:

1. Did the agent actually dial, and dial *this* number? Numbers are
   assigned per start; an old one does not work.
2. Is the agent calling from a number the target expects? A call from an
   unlisted caller number is refused, and the agent's side sees a busy
   line.
3. Was the simulation still on? Check the turn-off time against when the
   call was placed.
4. Did the calls arrive faster than the target's limit for calls at once?
   Extra calls are refused rather than queued.

## Pitfalls

- **Do not use `run_simulation` for an agent that dials.** There is nothing
  for it to call.
- **Do not confuse this with "the caller opens".** A normal simulation where
  the simulated caller speaks first is still Okareo dialing the agent.
- **The number is temporary.** Never save it in the agent's configuration
  as a permanent test line; it goes back to the pool when the simulation
  is turned off.
- **Restricting caller numbers is a safety measure, not a nuisance.** While
  the simulation is on, anyone who dials the number reaches the simulated
  person unless the target lists who may call.
- **This needs a paid plan.** A trial organization is refused when
  starting, and the refusal says so.
