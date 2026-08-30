"""
Bilingual lexicon for routing a patient's chief complaint to a
question-tree branch.

Deliberately much larger than the short keyword tuples embedded on each
ComplaintCategory in question_tree.py, and separate so growing it never
touches routing logic. Each category lists the wordings a patient (or
attendant) actually uses in the ED intake at this site: English, Hindi in
Devanagari, romanized Hindi, and the code-mixed Hinglish that dominates
Delhi/NCR triage speech. Common misspellings and ASR mistranscriptions
(e.g. "seene mein dard" heard as "sine mein dard") are included, since
this file exists to be robust to how people actually say things, not to
how a spelling checker would prefer them.

Use through classify_complaint() in question_tree.py; this module is
purely data and imports nothing from the tree or the pipeline. The list
is illustrative, not exhaustive -- adding more phrasings later means
appending to the relevant tuple, not touching any function.

The keyword sets DO NOT decide clinical acuity: they only pick which
question BLOCK to ask next. The red-flag table (intake/red_flags.py) is
still the only thing that maps observations to a band.
"""

from __future__ import annotations

# Category name -> tuple of substring keywords (case-insensitive, matched
# after apostrophe stripping; see classify_complaint()'s keyword layer).
# Keep entries as lowercase, apostrophe-free strings for that reason.
# Ordering within each tuple has no functional meaning.
EXPANDED_KEYWORDS: dict = {
    "choking": (
        "choking", "choked", "cant swallow", "cannot swallow", "trouble swallowing",
        "difficulty swallowing", "swallowed something", "swallowed a coin",
        "swallowed a bone", "swallowed a battery", "something stuck in throat",
        "something in my throat", "food stuck", "fish bone stuck", "bone stuck",
        "stuck in throat", "stuck in my throat", "obstructed airway",
        "gasping for air", "cant breathe stuck", "gale mein kuch phas gaya",
        "gale mein phas gaya", "gale mein atak gaya", "kuch nigal liya",
        "kuch phas gaya", "phas gaya gale", "gale mein",
        "dum ghut raha hai", "saans nahi aa rahi kuch phasa",
        "गले में कुछ फँस गया", "गले में अटक गया", "निगल लिया", "साँस रुक रही है",
    ),

    "seizure": (
        "seizure", "seizures", "convulsion", "convulsions", "convulsing",
        "fit", "fits", "epileptic fit", "epilepsy attack", "epileptic attack",
        "jerking movements", "shaking uncontrollably", "shaking all over",
        "twitching all over", "eyes rolled back", "tongue bitten",
        "passed out shaking", "lost consciousness and shaking",
        "unconscious with jerks", "post ictal", "postictal",
        "daura", "daura pada", "daure aa rahe hain", "mirgi", "mirgi ka daura",
        "jhatke aa rahe hain", "jhatke lag rahe", "kaanp raha hai",
        "behosh ho gaya aur jhatke", "aankhein chadh gayi",
        "दौरा", "दौरा पड़ा", "मिर्गी", "झटके आ रहे हैं", "बेहोश हो गया",
    ),

    "sudden_weakness_speech": (
        "stroke", "brain stroke", "mini stroke", "tia", "cva",
        "sudden weakness", "sudden numbness", "one side weak", "one side weakness",
        "left side weak", "right side weak", "left arm weak", "right arm weak",
        "left leg weak", "right leg weak", "went weak on one side",
        "cannot lift arm", "cant lift arm", "cant lift leg", "arm fell down",
        "face drooping", "face dropped", "one side of face", "smile crooked",
        "smile is uneven", "mouth pulling to one side",
        "cant speak properly", "cannot speak properly", "slurred speech",
        "speech is slurred", "speech went funny", "words not coming out",
        "unable to speak", "trouble finding words", "speech difficulty",
        "numbness in face", "tingling on one side", "numb on left", "numb on right",
        "vision went dark", "sudden vision loss one eye",
        "ek taraf kamzori", "ek taraf sun ho gaya", "chehra tedha",
        "chehra ek taraf lataka", "bolne mein taklif", "boli lad rahi hai",
        "haath uth nahi raha", "pair uth nahi raha", "muh tirchha",
        "एक तरफ़ कमज़ोरी", "एक तरफ़ सुन्न", "चेहरा टेढ़ा", "बोलने में तकलीफ", "पक्षाघात",
    ),

    "poisoning_bite": (
        "poison", "poisoned", "poisoning", "took poison", "drank poison",
        "swallowed poison", "chemical poisoning", "kerosene", "pesticide",
        "insecticide", "phenyl", "detergent swallowed", "acid swallowed",
        "overdose", "overdosed", "took extra pills", "took too many pills",
        "took a lot of tablets", "sleeping pills overdose",
        "attempted suicide by pills", "tried to end life pills",
        "snake bite", "snakebite", "bitten by snake", "saanp ne kata",
        "cobra bite", "krait bite", "russell viper",
        "scorpion bite", "scorpion sting", "bichhu ne kata", "bichhu",
        "dog bite", "bitten by dog", "kutte ne kata", "monkey bite",
        "cat bite", "insect bite", "wasp sting", "bee sting", "hornet sting",
        "spider bite", "rat bite", "chuha kaat liya",
        "zeher", "zeher liya", "keede ne kata", "जहर", "जहर खा लिया",
        "साँप ने काटा", "कुत्ते ने काटा", "बिच्छू ने काटा",
        "medicine overdose", "drug overdose", "took multiple tablets",
    ),

    "chest_pain": (
        "chest pain", "chest pains", "pain in chest", "pain in my chest",
        "chest hurts", "chest is hurting", "chest tightness", "tight chest",
        "chest pressure", "pressure on chest", "heavy chest",
        "elephant on my chest", "band around chest",
        "chest discomfort", "chest heaviness", "chest ache",
        "crushing chest pain", "burning in chest", "burning chest",
        "sharp chest pain", "stabbing chest pain", "dull chest pain",
        "left chest pain", "right chest pain", "center chest pain",
        "chest pain radiating", "pain going to arm", "pain going to jaw",
        "chest mein pain", "chest me pain", "chest me dard",
        "seene mein dard", "seene me dard", "sine mein dard", "chhati mein dard",
        "chhati me dard", "dil mein dard", "dil me dard",
        "seene mein bhaari", "chhati bhaari",
        "palpitations", "heart racing", "heart pounding", "heart fluttering",
        "irregular heartbeat", "skipped beats", "heartbeat fast",
        "dil dhadakna", "dil ki dhadkan tez", "dil bahut zor se dhadak raha",
        "dil me halchal",
        "सीने में दर्द", "छाती में दर्द", "दिल में दर्द", "सीना भारी", "धड़कन तेज़",
        "heart attack", "heart attack ho raha", "dil ka daura",
    ),

    "pregnancy_labour": (
        "labour", "labor", "in labour", "in labor", "labor pain", "labour pain",
        "labor pains", "contractions", "contractions started",
        "contractions every", "contractions coming",
        "pregnant and pain", "pregnant with pain", "pregnancy pain",
        "water broke", "waters broke", "water broken", "amniotic fluid",
        "leaking fluid pregnant", "fluid leaking below", "prasav",
        "prasav peeda", "bacha hone wala", "delivery ka time",
        "contractions shuru", "pani nikal gaya", "pani toot gaya",
        "प्रसव", "प्रसव पीड़ा", "पानी टूट गया", "गर्भावस्था में दर्द",
        "pregnant and bleeding", "bleeding pregnant", "pregnancy bleeding",
        "pregnant with spotting",
    ),

    "vaginal_bleeding": (
        "vaginal bleeding", "vaginal bleed", "bleeding down there",
        "bleeding from vagina", "heavy bleeding period", "heavy period",
        "period wont stop", "period not stopping", "menstrual bleeding heavy",
        "spotting", "post menopause bleeding", "postmenopausal bleeding",
        "bleeding after menopause", "bleeding after sex",
        "irregular bleeding", "bleeding between periods",
        "yoni se khoon", "peshab ki jagah se khoon",
        "mahwari band nahi ho rahi", "mahavari jyada",
        "योनि से खून", "मासिक धर्म का ज़्यादा खून",
    ),

    "breathing_difficulty": (
        "difficulty breathing", "difficulty in breathing", "cant breathe",
        "cannot breathe", "unable to breathe", "hard to breathe",
        "breathless", "breathlessness", "short of breath", "shortness of breath",
        "gasping", "gasping for breath", "panting", "wheezing",
        "sob", "dyspnea", "dyspnoea",
        "cant catch my breath", "out of breath", "winded",
        "asthma attack", "asthma", "inhaler not working",
        "copd flare", "chronic bronchitis", "bronchitis",
        "pneumonia symptoms", "chest infection",
        "saans lene mein taklif", "saans phool rahi hai",
        "saans nahi aa rahi", "dum ghut raha", "haanphni",
        "dama ka daura", "dama", "asthama",
        "साँस लेने में तकलीफ", "साँस फूल रही है", "दमा का दौरा", "साँस नहीं आ रही",
    ),

    "bleeding_wound": (
        "cut", "deep cut", "laceration", "laceration bleeding",
        "wound", "open wound", "gaping wound", "puncture wound",
        "bleeding wound", "blood flowing", "gushing blood",
        "wont stop bleeding", "cannot stop bleeding", "bleeding heavily",
        "artery cut", "vein cut", "stab wound", "stabbed",
        "knife wound", "glass cut", "sharp object cut",
        "wound not closing", "bleeding from arm", "bleeding from leg",
        "bleeding from head", "scalp laceration",
        "khoon beh raha hai", "khoon nikal raha", "khoon band nahi ho raha",
        "gehra ghav", "ghav se khoon",
        "खून बह रहा है", "गहरा घाव", "खून बंद नहीं हो रहा", "चोट से खून",
    ),

    "burns": (
        "burn", "burns", "burnt", "burned", "got burnt", "got burned",
        "scald", "scalded", "scalding water", "hot water burn",
        "chemical burn", "acid burn", "electrical burn", "electric shock burn",
        "fire burn", "flame burn", "grease burn", "steam burn",
        "third degree burn", "second degree burn", "first degree burn",
        "blistering burn", "peeling skin burn",
        "jal gaya", "jal gayi", "jala hua", "aag se jal gaya",
        "garam paani se jal gaya", "tel se jala",
        "जल गया", "जल गयी", "आग से जला", "तेज़ाब से जला",
    ),

    "injury": (
        # NOTE: bare "hurt" / "got hurt" are deliberately excluded -- they
        # match inside "throat hurts", "stomach hurts", "head hurts" and
        # would hijack every symptom to the injury branch. Use only the
        # more specific mechanism phrases below.
        "injury", "injured", "accident", "road accident",
        "traffic accident", "bike accident", "car accident", "scooter accident",
        "auto accident", "hit by vehicle", "hit by car", "hit by bike",
        "run over", "ran over foot", "fell", "fall", "fell down",
        "fell from stairs", "fell from height", "fell from bike",
        "slipped and fell", "tripped and fell", "fell on face",
        "fell on head", "head injury", "hit head", "banged head",
        "hit by ball", "hit by stick", "beaten", "assault", "attacked",
        "fight injury", "hit by someone",
        "sprain", "sprained ankle", "twisted ankle", "twisted knee",
        "fracture", "possible fracture", "bone broken", "broke my arm",
        "broke my leg", "dislocated shoulder",
        "chot", "chot lag gayi", "gir gaya", "gir gayi", "gir pada",
        "chhat se gira", "seedhi se gira", "gaadi ne takkar mari",
        "haath toot gaya", "pair toot gaya", "haddi toot gayi",
        "चोट", "गिर गया", "गिर गयी", "एक्सीडेंट", "हड्डी टूट गयी", "फ्रैक्चर",
    ),

    "abdominal_pain": (
        "abdominal pain", "abdomen pain", "abdomen hurts", "abdomen hurting",
        "stomach pain", "stomach ache", "stomach ache severe", "stomach hurts",
        "stomach hurting", "my stomach", "stomach cramps", "cramps in stomach",
        "belly pain", "belly hurts", "belly ache", "tummy pain", "tummy hurts",
        "tummy ache", "upper abdomen pain", "lower abdomen pain",
        "right side abdomen pain", "left side abdomen pain", "epigastric pain",
        "gastric pain", "gas pain", "acidity pain", "acid reflux pain",
        "gallbladder pain", "appendix pain", "possible appendicitis",
        "pain around navel", "pain near belly button",
        "pet mein dard", "pet me dard", "pet dard", "pet dukh raha hai",
        "pet mein bahut dard", "pet phool gaya", "pet mein aithan",
        "pet mein marod", "gaith mein dard", "pait mein dard",
        "पेट में दर्द", "पेट दर्द", "पेट फूल गया", "पेट में मरोड़", "पेट में गैस",
    ),

    "vomiting": (
        "vomiting", "vomit", "vomited", "throwing up", "threw up",
        "keep vomiting", "cannot stop vomiting", "vomiting blood",
        "hematemesis", "bloody vomit", "coffee ground vomit",
        "projectile vomiting", "green vomit", "yellow vomit",
        "vomiting after eating", "nausea", "nauseous", "nauseated",
        "feeling sick to stomach", "queasy",
        "ulti", "ulti aa rahi hai", "ulti ho rahi hai", "ulti hui",
        "ulti me khoon", "matli", "matli aa rahi hai", "jee michlana",
        "jee ghabra raha hai", "ubkai aa rahi hai",
        "उल्टी", "उल्टी हो रही है", "उल्टी में खून", "जी मिचला रहा है", "मतली",
    ),

    "diarrhea": (
        "diarrhea", "diarrhoea", "loose motion", "loose motions",
        "loose stool", "loose stools", "watery stool", "watery motion",
        "watery diarrhea", "bloody stool", "blood in stool", "black stool",
        "melena", "dysentery", "food poisoning", "stomach infection",
        "gastro", "gastroenteritis", "traveller diarrhea",
        "many times a day motion", "cant control stool",
        "dast", "dast lag rahe hain", "patli dast", "khooni dast",
        "kale dast", "dast me khoon", "peshab jaisa dast",
        "food poisoning ho gaya", "gaith kharab ho gaya",
        "दस्त", "दस्त लग रहे हैं", "पतले दस्त", "खूनी दस्त", "पेट खराब",
    ),

    "fever": (
        "fever", "high fever", "low grade fever", "chronic fever",
        "recurring fever", "fever on and off", "spiking fever",
        "fever for days", "fever from morning", "fever last night",
        "fever with chills", "fever with rash", "fever and cough",
        "fever and vomiting", "fever and headache",
        "temperature 100", "temperature 101", "temperature 102",
        "temperature 103", "temperature 104", "high temperature",
        "malaria", "typhoid", "dengue", "dengue fever", "chikungunya",
        "covid", "covid symptoms", "flu", "influenza",
        "bukhar", "bukhaar", "tez bukhar", "halka bukhar",
        "kai din se bukhar", "bukhar aa jaa raha hai", "sardi ke saath bukhar",
        "malaria ho gaya", "typhoid ho sakta", "dengue ho sakta",
        "बुखार", "तेज़ बुखार", "मलेरिया", "टाइफाइड", "डेंगू", "बुखार कई दिन से",
    ),

    "cough_cold": (
        "cough", "cough for days", "chronic cough", "productive cough",
        "dry cough", "wet cough", "cough with mucus", "cough with sputum",
        "cough with blood", "hemoptysis", "coughing up blood",
        "cold", "runny nose", "blocked nose", "stuffy nose",
        "congestion", "nasal congestion", "sinus congestion",
        "sneezing", "post nasal drip", "chest congestion",
        "sinusitis", "sinus infection", "bronchitis symptoms",
        "khansi", "khaansi", "sookhi khansi", "balgam wali khansi",
        "khansi me khoon", "sardi", "sardi zukam", "zukam",
        "naak band", "naak beh rahi", "cheenkein aa rahi",
        "खाँसी", "सूखी खाँसी", "बलगम वाली खाँसी", "सर्दी", "जुकाम", "नाक बंद",
    ),

    "sore_throat": (
        "sore throat", "throat pain", "throat hurts", "painful throat",
        "throat infection", "tonsils pain", "tonsillitis",
        "hoarse voice", "lost voice", "voice gone", "cant speak throat",
        "difficulty swallowing", "painful swallowing",
        "gala dukh raha hai", "gale mein dard", "gale mein kharaash",
        "gala baith gaya", "aawaz nahi nikal rahi",
        "गले में दर्द", "गला बैठ गया", "गले में खराश", "टॉन्सिल",
    ),

    "headache": (
        "headache", "headaches", "bad headache", "severe headache",
        "worst headache", "thunderclap headache", "sudden headache",
        "migraine", "migraine attack", "migraine aura",
        "tension headache", "cluster headache",
        "head pain", "head hurts", "head throbbing", "throbbing headache",
        "one sided headache", "back of head pain", "front of head pain",
        "dizzy", "dizziness", "spinning", "vertigo",
        "lightheaded", "light headed", "faint", "faintness",
        "fainting", "fainted", "passed out", "collapsed",
        "sar dard", "sar mein dard", "sardard", "sir dard",
        "aadha sir dard", "sar bhaari", "chakkar", "chakkar aana",
        "chakkar aa rahe hain", "bhram", "behosh ho gaya",
        "सर दर्द", "सिर में दर्द", "आधे सिर का दर्द", "चक्कर", "बेहोशी",
    ),

    "weakness_fatigue": (
        "weakness", "generalized weakness", "whole body weakness",
        "feeling weak", "no strength", "no energy", "energy less",
        "fatigue", "chronic fatigue", "tired all the time",
        "tiredness", "exhausted", "exhaustion", "cant get out of bed",
        "lethargic", "lethargy", "sluggish", "very sleepy",
        "kamzori", "kamzor", "bahut kamzori", "thakan", "thak gaya",
        "shareer me jaan nahi", "uth nahi pa raha",
        "कमज़ोरी", "थकान", "बहुत थका हुआ", "शरीर में जान नहीं",
    ),

    "back_neck_pain": (
        "back pain", "backache", "lower back pain", "upper back pain",
        "back pain radiating", "sciatica", "sciatic pain", "lumbago",
        "slipped disc", "disc pain", "spine pain", "spinal pain",
        "neck pain", "stiff neck", "neck stiffness", "cervical pain",
        "neck spasm", "neck cant move", "neck locked",
        "peeth dard", "peeth mein dard", "kamar dard", "kamar mein dard",
        "gardan dard", "gardan me dard", "gardan akad gayi", "gardan mein khichaav",
        "पीठ में दर्द", "कमर दर्द", "गर्दन दर्द", "गर्दन अकड़ गयी",
    ),

    "limb_joint_pain": (
        "joint pain", "joint pains", "arthritis pain", "arthritis flare",
        "gout", "gouty attack",
        "knee pain", "shoulder pain", "elbow pain", "wrist pain",
        "ankle pain", "hip pain", "finger pain", "toe pain",
        "arm pain", "leg pain", "muscle pain", "muscle ache",
        "cramp", "muscle cramp", "leg cramp", "calf cramp",
        "swollen knee", "swollen ankle", "swollen finger",
        "jodo mein dard", "jodo ka dard", "ghutne mein dard", "kandhe mein dard",
        "haath mein dard", "pair mein dard", "koohni mein dard",
        "kalai mein dard", "aithan aa gayi", "pindli me dard",
        "जोड़ों में दर्द", "घुटने में दर्द", "कंधे में दर्द", "पैर में दर्द",
    ),

    "rash_allergy": (
        "rash", "rashes", "skin rash", "red rash", "itchy rash",
        "spreading rash", "sudden rash", "hives", "urticaria",
        "welts", "wheals", "itching", "itchy all over", "itching everywhere",
        "allergic reaction", "allergy", "food allergy", "drug allergy",
        "medication reaction", "peanut allergy",
        "anaphylaxis", "throat closing allergy", "swelling face allergy",
        "swollen lips allergy", "swollen tongue allergy",
        "eczema flare", "psoriasis flare", "contact dermatitis",
        "khujli", "khaaj", "chakatte", "chakatte pad gaye",
        "sharir par daane", "daane nikal aaye", "allergy ho gayi",
        "kuch kha ke sujan aa gayi", "hoth soojh gaye",
        "दाने", "खुजली", "चकत्ते", "एलर्जी", "सूजन एलर्जी",
    ),

    "swelling": (
        "swelling", "swollen", "puffy", "puffiness", "edema", "oedema",
        "pitting edema", "ankle swelling", "leg swelling", "feet swelling",
        "face swelling", "eye swelling", "lymph node swelling",
        "gland swelling", "abdominal swelling", "abdominal distension",
        "swollen belly", "swelling one side", "sudden swelling",
        "sujan", "soojan", "sooj gaya", "sooj gayi", "phool gaya",
        "chehra sooj gaya", "haath sooj gaya", "pair sooj gaya",
        "gaanth", "gaanth nikal aayi",
        "सूजन", "सूज गया", "फूल गया", "गाँठ",
    ),

    "eye_problem": (
        "eye pain", "eye ache", "burning eyes", "red eye", "red eyes",
        "eye redness", "watery eyes", "discharge from eye",
        "conjunctivitis", "pink eye", "sty", "stye",
        "vision problem", "blurry vision", "blurred vision",
        "double vision", "diplopia", "cant see", "cannot see",
        "loss of vision", "sudden vision loss", "dark spots vision",
        "flashes in vision", "floaters", "eye injury", "something in eye",
        "chemical in eye", "eye trauma",
        "aankh mein dard", "aankh laal", "aankh se paani",
        "aankhon mein dikhna band", "dhundhla dikhna",
        "aankhon me chubhan", "aankh mein kuch chala gaya",
        "आँख में दर्द", "आँख लाल", "धुंधला दिखना", "आँख से पानी", "आँख में चोट",
    ),

    "ear_problem": (
        "ear pain", "ear ache", "earache", "ear infection",
        "hearing problem", "cant hear", "cannot hear", "hearing loss",
        "sudden hearing loss", "muffled hearing",
        "ear discharge", "pus from ear", "fluid from ear",
        "bleeding from ear", "blood from ear", "ear ringing",
        "tinnitus", "buzzing in ear", "vertigo ear",
        "kaan mein dard", "kaan dard", "kaan se paani", "kaan se peep",
        "kaan me sunai nahi", "kaan sunna band",
        "कान में दर्द", "कान से पानी", "कान से खून", "कम सुनाई देना",
    ),

    "dental_pain": (
        "tooth pain", "toothache", "tooth ache", "dental pain",
        "mouth pain", "gum pain", "gum swelling", "gum bleeding",
        "dental abscess", "tooth abscess", "broken tooth", "chipped tooth",
        "tooth knocked out", "jaw pain", "jaw swelling",
        "wisdom tooth pain", "post extraction bleeding",
        "dant dard", "dant mein dard", "mooh mein dard", "mooh me chhale",
        "masudo mein dard", "masudo se khoon", "jabde mein dard",
        "दाँत में दर्द", "मुँह में दर्द", "मसूड़ों से खून", "जबड़े में दर्द",
    ),

    "urinary": (
        "urinary", "urine", "urination", "urinary infection", "uti",
        "urinary tract infection", "bladder infection", "cystitis",
        "kidney infection", "pyelonephritis",
        "burning urination", "painful urination", "dysuria",
        "frequent urination", "urinary urgency", "cant hold urine",
        "unable to urinate", "cannot urinate", "urinary retention",
        "blood in urine", "hematuria", "cloudy urine", "smelly urine",
        "kidney stone", "kidney stones", "renal colic", "flank pain kidney",
        "peshab mein jalan", "peshab me dard", "peshab band ho gaya",
        "peshab nahi aa raha", "peshab me khoon", "pathri", "gurde ki pathri",
        "पेशाब में जलन", "पेशाब में खून", "पेशाब बंद", "पथरी",
    ),

    "diabetic_emergency": (
        "diabetic", "diabetes", "sugar", "blood sugar", "sugar level",
        "hypoglycemia", "hypo", "low sugar", "sugar dropped",
        "hyperglycemia", "high sugar", "sugar very high", "dka",
        "diabetic ketoacidosis", "hhs", "hyperosmolar",
        "took insulin no food", "missed insulin", "skipped insulin",
        "extra insulin", "insulin overdose", "sugar dropped after exercise",
        "diabetic feeling weak", "sweating shaking diabetic",
        "shakkar", "sugar kam ho gaya", "sugar zyada ho gaya",
        "sugar level kam", "sugar level zyada", "insulin le liya khaana nahi khaya",
        "शुगर कम", "शुगर ज़्यादा", "इंसुलिन ले ली खाना नहीं खाया", "मधुमेह",
    ),

    "mental_health": (
        "want to end my life", "want to die", "kill myself", "suicide",
        "suicidal", "suicidal thoughts", "thinking of ending it",
        "life is not worth", "cannot go on", "hurt myself", "self harm",
        "self-harm", "cut myself", "cutting", "overdose intentional",
        "took pills to", "took pills to end", "took pills to die",
        "hanging attempt", "tried to jump",
        "panic attack", "anxiety attack", "cant calm down",
        "depression severe", "very depressed", "worthless feeling",
        "cant sleep for days", "hallucinating", "seeing things",
        "hearing voices", "voices telling me",
        "khud ko marna", "jaan dena", "jaan de dungi", "khudkushi",
        "khudkushi karni hai", "khud ko nuksaan pahunchana",
        "बहुत उदास", "जान देना चाहता हूँ", "खुद को मारना",
        "कुछ अच्छा नहीं लगता", "आवाज़ें सुनाई देती हैं",
    ),

    # New categories introduced to hit broader coverage of what an ED
    # actually sees. Follow-ups reuse the shared "generic" block if a
    # matching ComplaintCategory has not yet been added in question_tree.py.
    "cardiac_palpitations": (
        "palpitations", "heart racing", "heart pounding", "heart flutter",
        "heart skipping", "skipped beats", "extra beats",
        "irregular heartbeat", "arrhythmia", "atrial fibrillation",
        "fast heartbeat", "slow heartbeat", "pounding in chest",
        "feeling my heart beat", "dhadkan tez", "dhadkan tez ho rahi",
        "dhadkan bahut zor se", "dil zor se dhadak raha",
        "धड़कन तेज़", "धड़कन असामान्य", "दिल ज़ोर से धड़क रहा",
    ),

    "syncope": (
        "fainted", "passed out", "syncope", "vasovagal", "blackout",
        "collapsed", "briefly unconscious", "fainted while standing",
        "fainted at work", "lost consciousness briefly",
        "behosh ho gaya kuch der", "gir gaya behosh", "aankhon ke aage andhera",
        "बेहोश हो गया थोड़ी देर", "चक्कर आके गिर गया", "आँखों के आगे अंधेरा",
    ),

    "genitourinary_male": (
        "testicle pain", "testicular pain", "scrotal pain", "scrotal swelling",
        "swollen testicle", "groin pain", "hernia", "swelling in groin",
        "erection painful", "priapism", "unable to pass urine male",
        "andkosh mein dard", "kokh mein dard",
    ),

    "pediatric_illness": (
        "child fever", "baby fever", "infant fever", "child not feeding",
        "baby not feeding", "child vomiting", "baby vomiting",
        "child diarrhea", "baby diarrhea", "child rash",
        "baby crying non stop", "baby wont stop crying",
        "child unresponsive", "baby unresponsive",
        "bacha ro raha hai", "bacha nahi kha raha", "bacha behosh",
        "बच्चा रो रहा है", "बच्चा नहीं खा रहा", "बच्चे को बुखार",
    ),

    "obstetric_generic": (
        "pregnancy problem", "pregnant with", "pregnant and", "gestation",
        "morning sickness severe", "hyperemesis",
        "reduced fetal movement", "baby not moving", "baby moving less",
        "preterm", "premature labour",
        "गर्भावस्था में समस्या", "बच्चा नहीं हिल रहा",
    ),
}


def merge_into(existing_keywords: dict) -> dict:
    """
    Return a new {category -> tuple(keywords)} that is `existing_keywords`
    from question_tree.py extended with EXPANDED_KEYWORDS, preserving
    per-category order (existing first, then new-and-unique).

    Called once at import in question_tree.py; not called at request time.
    """
    merged = {}
    for name, kws in existing_keywords.items():
        seen = set(kws)
        extras = tuple(k for k in EXPANDED_KEYWORDS.get(name, ()) if k not in seen)
        merged[name] = tuple(kws) + extras
    # Categories that appear ONLY in the expanded set (no matching
    # ComplaintCategory yet) still get a keyword entry so future tree
    # additions can wire straight in; the fallback layer will pass them
    # through to "generic" until a real branch exists.
    for name, kws in EXPANDED_KEYWORDS.items():
        merged.setdefault(name, tuple(kws))
    return merged


def total_keyword_count(merged: dict) -> int:
    return sum(len(v) for v in merged.values())


# Longest matched keyword this length or more is accepted as a confident
# routing signal (that is, the LLM classifier is skipped). Below it, we
# still return a best-effort category name, and the caller decides whether
# to trust it or fall back to the LLM. Picked empirically: 5 characters
# covers "fever" / "burn" / "sugar" / "dast" / "chot" and rules out
# incidental matches like "or" / "in" inside a longer phrase.
LEXICON_CONFIDENCE_MIN_LEN = 5


def score_categories(text: str, keyword_map: dict) -> list:
    """
    Score every category against `text` by the length of its longest
    matching keyword. Longer keywords are more specific, so this favours
    "crushing chest pain" (chest_pain, score 19) over "pain" (many
    categories, score 4).

    Case- and apostrophe-insensitive; keyword_map keys are the category
    names, values are iterables of keyword strings.

    Returns a list of (category_name, best_matched_keyword_length) sorted
    strongest first. Categories with zero matches are omitted, so the
    result may be empty.
    """
    if not text:
        return []
    normalized = text.lower().replace("'", "")
    scores = []
    for name, kws in keyword_map.items():
        best = 0
        for kw in kws:
            if kw and kw in normalized and len(kw) > best:
                best = len(kw)
        if best > 0:
            scores.append((name, best))
    scores.sort(key=lambda pair: -pair[1])
    return scores


def top_category(text: str, keyword_map: dict) -> tuple:
    """
    Convenience wrapper: return (best_category, best_score) or (None, 0).
    """
    scored = score_categories(text, keyword_map)
    return scored[0] if scored else (None, 0)
