"""Fictional resident interviews. Analysis is performed separately on their text."""

import random
from datetime import date, timedelta

from core.models import Asset, LeaseRecord, ResidentFeedback
from core.portfolio.locations import LOCATIONS
from core.portfolio.tenant_names import generated_tenant_name

AS_OF = date(2026, 9, 15)
# Recommendation responses, independent of the sentiment analyzer.
RESPONSE_MIX = ((30, 12, 8), (20, 13, 17), (25, 15, 10), (23, 15, 12), (28, 12, 10), (33, 10, 7))
EXPERIENCES = {
    "Maintenance": {
        "positive": ["The air conditioning repair was completed the same day, and the technician left everything tidy.", "The maintenance team arrived on time and fixed the leaking tap on the first visit."],
        "negative": ["The air conditioning is still unreliable after two visits, and sleeping in a warm bedroom has been frustrating.", "The leaking tap has been reported three times but the maintenance ticket keeps being closed without a repair."],
        "neutral": ["The annual air conditioning inspection was completed during the scheduled window.", "I have a routine maintenance visit booked for next week and cannot comment on the result yet."],
    },
    "Communication": {
        "positive": ["The resident services team kept me updated without needing reminders, which I really appreciated.", "My questions were answered clearly by a friendly member of the resident services team."],
        "negative": ["I had to chase resident services four times and still did not get a clear update.", "The messages from resident services contradicted each other, which made a simple request stressful."],
        "neutral": ["Resident services sent the standard update by email and I have no further questions.", "I normally receive community notices by email and check them at the weekend."],
    },
    "Parking": {
        "positive": ["Visitor parking has been easy to arrange, even when my family comes at the weekend.", "My allocated parking space is convenient and the new signs make access much easier."],
        "negative": ["Visitor parking fills up every evening and my guests have had to circle for twenty minutes.", "Cars keep blocking the parking ramp and the repeated delays are becoming very irritating."],
        "neutral": ["I use my allocated parking space during the week and rarely need visitor parking.", "I have one parking permit and the renewal date is on my calendar."],
    },
    "Facilities": {
        "positive": ["The swimming pool is well maintained and our family loves spending time there.", "The gym equipment is in good condition and the opening hours suit my routine very well."],
        "negative": ["The swimming pool has been closed repeatedly with very little notice, which has been disappointing.", "Several machines in the gym have been broken for weeks and it feels like nobody is following up."],
        "neutral": ["I have not used the swimming pool recently, so I cannot give an opinion about it.", "The gym opens at six and I normally visit twice a month."],
    },
    "Cleanliness": {
        "positive": ["The corridors and lifts are consistently clean, and the housekeeping team is very considerate.", "The waste collection area is much cleaner now and I appreciate the regular housekeeping visits."],
        "negative": ["The waste collection area smells unpleasant and rubbish sometimes remains there overnight.", "The lift floors and corridors have been dirty several mornings in a row, which is disappointing."],
        "neutral": ["Housekeeping visits our corridor in the morning and waste collection is in the evening.", "I use the recycling point beside the waste collection area once a week."],
    },
    "Renewals": {
        "positive": ["The lease renewal process was straightforward and every charge was explained before I signed.", "The renewal reminder arrived early and the leasing team helped me complete everything smoothly."],
        "negative": ["The lease renewal notice arrived late and the unexplained charges have left me unhappy.", "I received different answers about the renewal increase and I am worried about the lack of clarity."],
        "neutral": ["My lease renewal is due in November and I have not made a decision yet.", "I received the renewal documents and am reading the terms before responding."],
    },
    "Noise": {
        "positive": ["The evenings have been peaceful and the quiet surroundings help me relax after work.", "The team handled the noise complaint quickly and the nights have been quiet since then."],
        "negative": ["Late-night noise from the neighbouring apartment has disturbed my sleep several times this month.", "Construction noise starts early and the lack of advance notice makes working from home difficult."],
        "neutral": ["I work away from home most days and have not noticed a change in noise levels.", "I was told the daytime work would finish next month and have noted the schedule."],
    },
    "Security": {
        "positive": ["The security team is welcoming and handles visitor access efficiently, which makes us feel comfortable.", "The security staff helped my parents find our building and were patient and professional."],
        "negative": ["Visitor access takes too long and the security team gives different instructions on each visit.", "The access card has failed twice and the long wait at the security desk has been frustrating."],
        "neutral": ["I use an access card for the entrance and register visitors through the usual process.", "The security desk has my current vehicle registration and contact number."],
    },
    "Landscaping": {
        "positive": ["The gardens are beautifully maintained and the shaded walking paths are a highlight of living here.", "The landscaped courtyards feel welcoming and the gardening team has done an excellent job."],
        "negative": ["Several garden lights are broken and the neglected planting makes the walking paths less inviting.", "The irrigation leaves large puddles across the walking paths and repeated reports have not helped."],
        "neutral": ["The gardening team visits on weekday mornings and I usually walk through the courtyard after work.", "There is a landscaped path between my building and the main entrance."],
    },
}
FOCUS = (
    ("Maintenance", "Landscaping", "Facilities"), ("Parking", "Maintenance", "Security"),
    ("Noise", "Cleanliness", "Communication"), ("Facilities", "Noise", "Communication"),
    ("Landscaping", "Maintenance", "Renewals"), ("Facilities", "Landscaping", "Parking"),
)


def populate_feedback():
    created = 0
    for index, location in enumerate(LOCATIONS):
        asset = Asset.objects.get(name=location["name"])
        residents = list(LeaseRecord.objects.filter(asset=asset, origin="synthetic", data__occupancy_status="Occupied").order_by("code"))
        rng = random.Random(f"feedback-v1:{location['id']}")
        promoters, passives, detractors = RESPONSE_MIX[index]
        scores = [rng.choice([9, 10]) for _ in range(promoters)] + [rng.choice([7, 8]) for _ in range(passives)] + [rng.randint(2, 6) for _ in range(detractors)]
        rng.shuffle(scores)
        for number, score in enumerate(scores, 1):
            reference = f"FB-{location['id'].upper()}-{number:03d}"
            resident = residents[number - 1] if number <= len(residents) else None
            name = resident.data["tenant_name"] if resident else generated_tenant_name(reference)
            # A recommendation and the tone of one conversation need not agree.
            tone = "positive" if score >= 9 else "neutral" if score >= 7 else "negative"
            if number % 13 == 0:
                tone = "negative" if tone == "positive" else "positive"
            main = rng.choice(FOCUS[index])
            other = rng.choice([t for t in EXPERIENCES if t != main])
            secondary_tone = "neutral" if number % 5 == 0 else tone
            if number % 7 == 0:
                secondary_tone = "positive" if tone == "negative" else "negative"
            first = rng.choice(EXPERIENCES[main][tone])
            second = rng.choice(EXPERIENCES[other][secondary_tone])
            closing = {"positive": "Overall, I feel well looked after and would like the team to keep this standard.",
                       "negative": "I would like someone to take ownership and confirm what will happen next.",
                       "neutral": "For now I do not have a strong view either way; I will see how things develop."}[tone]
            transcript = (
                f"Agent: Thank you for speaking with us about your experience at {asset.name}. What has stood out over the past month?\n\n"
                f"Resident ({name}): {first}\n\n"
                f"Agent: Is there anything else about living in the community that you would like to share?\n\n"
                f"Resident: {second} {closing}\n\n"
                f"Agent: On a scale from 0 to 10, how likely are you to recommend {asset.name} to a friend or colleague?\n\n"
                f"Resident: My recommendation score is {score} out of 10.\n\n"
                "Agent: Thank you. Your comments have been recorded for the community team."
            )
            _, new = ResidentFeedback.objects.get_or_create(reference=reference, defaults={
                "asset": asset, "record": resident, "resident_name": name, "received_on": AS_OF - timedelta(days=rng.randrange(90)),
                "recommendation_score": score, "transcript": transcript, "origin": "synthetic",
                "source_metadata": {"generator": "resident-interviews-v1", "as_of": AS_OF.isoformat()},
            })
            created += new
    return created
