# Getting the right control pool

Ok, thank you for this comprehensive tutorial. I have about 6000 HaT patients. I can get 50x the number of candidates (300k), because I have a pool of 300 million. But I am struggling with selection criteria for that wide net. Here are a few ways I think I could do the parameters pulling from the database, and the limits I think it takes on

- I could get someone of the same sex who had a diagnosis that is new within the same three-month window, and it isn't hat or some other immune disease or some other GI disease. But then you remove people who have a GI disease, and you sometimes want to compare those two functions because if hat has a lot of GI conditions, you don't want to compare against people who have none.

- Comparing the same three month window and similar diseases but not hat. Well, if you do that then you could just be adding in confounding variables.

I feel like what I'm saying is I need to run match it before I start pulling patients, but I can't do that because I have to have a patient base by which I could run match it. So I have to pull some set of data. I could in theory just pull thirty million, but pulling thirty million in the hopes that I'll get three hundred thousand or maybe three million, and I'll figure three hundred thousand, and just like specific things like the month of their new diagnosis and their gender and like I don't know, some other measure of sickness or something. Like yeah, you have to give me some parameter by which I would really whittle down a three hundred million patient cluster to something that would be a worthwhile way to pick out that three hundred thousand patient population.

Yes, exactly, and your gunshot analogy exposes the trap beautifully.

For a HaT PheWAS, you **do not** want the equivalent of “controls who also got shot.” That would be like choosing controls because they already have the kind of phenotype you are trying to study. You want controls who had a comparable **chance to be observed**, not controls who had comparable outcomes.

So the better analogy is:

> If studying gunshot victims, compare them to people from the same observable healthcare universe at the same calendar time, with similar age/sex and similar healthcare contact, not to people who also got shot.

For HaT, the “entrance probability” piece is not “had GI/immune/allergy disease.” It is more like:

- Was in the database at the same time.

- Had enough medical record depth.

- Had enough clinic contact to receive diagnoses.

- Was similar in age/sex/race/ethnicity.

- Had similar pre-index healthcare utilization.

That helps control the boring but dangerous bias: HaT patients may look phenotypically rich simply because they are medically complicated, heavily worked up, or diagnosed in a specialty-care pathway.

But you are also right about the deeper limitation: this does **not** prove a phenotype is biologically unique to HaT. A PheWAS can tell you:

> Among similarly observable patients, HaT status is associated with higher/lower odds of phenotype X.

It cannot, by itself, fully tell you whether phenotype X is caused by HaT, caused by diagnostic workup, caused by ascertainment, or caused by some referral pathway.

So I’d frame the study as discovery/association, then protect it with sensitivity analyses.

A good design might have multiple comparator sets:

1.  **Primary controls**\
    Broad no-known-HaT controls matched on sex, index quarter, age, observation time, and utilization.

2.  **High-utilization controls**\
    Same as above, but require similar high pre-index encounter burden. This asks: “Is HaT still different from other heavily medicalized patients?”

3.  **Symptom-adjacent controls**\
    People with allergic/GI/immune-type diagnoses but no known HaT. This is not the primary comparator, but it asks: “Is HaT different from people who came into care for nearby reasons?”

4.  **Negative-control phenotypes**\
    Outcomes you do not expect HaT to affect. If these light up everywhere, you may be measuring medical-contact bias.

5.  **Pre-index-only vs post-index-only analyses**\
    If phenotypes explode after HaT diagnosis, that may be surveillance/workup. If they are enriched before index, that is stronger evidence they are part of the HaT phenotype.

In plain English: use broad matched controls to find the signal, then use stricter/weirder comparator groups to interrogate whether the signal is “HaT biology” or “HaT diagnostic pathway.”

The goal is not to create a perfect non-HaT twin. That probably does not exist. The goal is to make the comparison honest enough that when GI, allergy, autonomic, pain, connective-tissue, or psychiatric phenotypes appear, you can say what kind of bias you tried to rule out and what remains uncertain.