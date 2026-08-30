/**
 * Client-side Hindi translations for the most common backend tree prompts.
 *
 * The real 140-node tree in intake/question_tree.py currently ships with
 * only English prompts (its promptHi field is null for most nodes -- see
 * the module-level note there). Hand-translating every clinical prompt
 * needs a reviewer, not a guess; until that lands, this table covers the
 * prompts the patient will most often see, so switching to Hindi actually
 * changes what the kiosk says instead of speaking English words with a
 * Hindi accent.
 *
 * A prompt not in the table falls back to English. That is the honest
 * failure mode: a wrong Hindi translation would be worse than English --
 * an intake question the patient can misunderstand affects what the
 * red-flag table sees next. Add new entries here only when a Hindi
 * speaker has confirmed the translation.
 */

const HI: Record<string, string> = {
  // shared opening
  'What is bothering you today?': 'आज आपको क्या तकलीफ हो रही है?',
  'When did this start?': 'यह कब शुरू हुआ?',
  'On a scale of 0 to 10, how bad is it right now?': '0 से 10 के पैमाने पर, यह अभी कितना बुरा है?',

  // adult / adolescent tail
  'Could you be pregnant?': 'क्या आप गर्भवती हो सकती हैं?',
  'Have you already taken any pain-relief medicine?': 'क्या आपने पहले से कोई दर्द निवारक दवा ली है?',
  'Are you taking any regular medications?': 'क्या आप कोई नियमित दवा ले रहे हैं?',
  'Any past medical history we should know?': 'क्या कोई पुरानी बीमारी है जो हमें जाननी चाहिए?',

  // paediatric tail
  'Is the child feeding/drinking normally?': 'क्या बच्चा सामान्य रूप से खा-पी रहा है?',
  'How is the child behaving right now?': 'बच्चा अभी कैसा बर्ताव कर रहा है?',

  // geriatric tail
  'Compared to usual, how is their movement and alertness today?': 'हमेशा की तुलना में, आज उनकी चाल और सजगता कैसी है?',
  'Any falls, or any new confusion?': 'क्या कोई गिरना, या कोई नया भ्रम है?',

  // chest pain
  'Where exactly is the pain?': 'दर्द ठीक कहाँ है?',
  'What does the pain feel like — sharp, dull, crushing, or burning?': 'दर्द कैसा लगता है — तेज़, हल्का, दबाव जैसा, या जलन?',
  'Does the pain spread anywhere, like your arm, neck, or jaw?': 'क्या दर्द कहीं फैलता है, जैसे हाथ, गर्दन, या जबड़ा?',
  'Are you having any difficulty breathing?': 'क्या आपको साँस लेने में कोई तकलीफ है?',
  'Are you sweating, or feeling nauseous?': 'क्या आपको पसीना आ रहा है, या मिचली महसूस हो रही है?',
  'Which side, or is it both sides?': 'कौन सी तरफ, या दोनों तरफ?',
  'Does it get worse when you lie down flat?': 'क्या लेटने पर यह और बुरा हो जाता है?',
  'Any cough, or bringing up phlegm?': 'क्या खाँसी है, या बलगम आ रहा है?',

  // abdominal
  'What does the pain feel like — cramping, sharp, or a dull ache?': 'दर्द कैसा लगता है — ऐंठन, तेज़, या हल्का दर्द?',
  'Have you had any vomiting?': 'क्या आपको उल्टी हुई है?',
  'Any diarrhea or change in your bowel movements?': 'क्या दस्त या मल त्याग में कोई बदलाव है?',
  'Do you have a fever along with this?': 'क्या आपको इसके साथ बुखार भी है?',
  'Any burning or pain when you urinate?': 'क्या पेशाब करते समय जलन या दर्द है?',

  // breathing / cough
  'Did this come on suddenly, or gradually?': 'क्या यह अचानक हुआ, या धीरे-धीरे?',
  'Does anything bring it on, like exertion or lying down?': 'क्या किसी चीज़ से यह शुरू होता है, जैसे मेहनत या लेटना?',
  'Any chest pain along with it?': 'क्या इसके साथ सीने में दर्द भी है?',
  'Any wheezing or noisy breathing?': 'क्या साँस में सीटी जैसी आवाज़ या शोर है?',
  'How long have you had this?': 'यह कब से है?',
  'Is it a dry cough, or are you bringing up phlegm?': 'क्या यह सूखी खाँसी है, या बलगम आ रहा है?',
  'Any fever along with it?': 'क्या इसके साथ बुखार भी है?',
  'Any difficulty breathing?': 'क्या साँस लेने में कोई तकलीफ है?',

  // fever
  'Do you know your temperature, if it was measured?': 'क्या आपको अपना तापमान पता है, अगर मापा गया हो?',
  'How many days has the fever been there?': 'बुखार कितने दिनों से है?',
  'Any chills or shivering?': 'क्या ठंड लगना या कंपकंपी है?',
  'Do you have a cough?': 'क्या आपको खाँसी है?',
  'Is the fever there all the time, or does it come and go?': 'क्या बुखार हर समय है, या आता-जाता है?',
  'Any rash, or bleeding from the gums, nose, or in urine or stool?': 'क्या कोई दाने हैं, या मसूड़ों, नाक, पेशाब या मल में खून आ रहा है?',
  'Any recent travel, or mosquito bites you remember?': 'हाल में कोई यात्रा, या मच्छर के काटने की याद है?',

  // headache
  'Did this come on suddenly, or build up gradually?': 'यह अचानक शुरू हुआ, या धीरे-धीरे बढ़ा?',
  'Any weakness, numbness, or trouble speaking?': 'क्या कोई कमज़ोरी, सुन्नपन, या बोलने में तकलीफ है?',
  'Any vomiting along with it?': 'क्या इसके साथ उल्टी भी है?',
  'Any changes in your vision?': 'क्या आपकी नज़र में कोई बदलाव है?',
  'Did you actually lose consciousness, even briefly?': 'क्या आप सचमुच बेहोश हुए, थोड़ी देर के लिए भी?',

  // injury / bleeding
  'How did the injury happen?': 'चोट कैसे लगी?',
  'Where is the injury?': 'चोट कहाँ है?',
  'Is there any bleeding, and is it under control?': 'क्या कोई खून बह रहा है, और क्या वह नियंत्रण में है?',
  'Does it look out of shape, or is there swelling?': 'क्या यह टेढ़ा दिख रहा है, या सूजन है?',
  'Can you move and use the area normally?': 'क्या आप उस जगह को सामान्य रूप से हिला और इस्तेमाल कर पा रहे हैं?',
  'Did they lose consciousness at any point, even briefly?': 'क्या वे किसी भी समय बेहोश हुए, थोड़ी देर के लिए भी?',
  'Any pain in the head, neck, or back?': 'क्या सिर, गर्दन, या पीठ में कोई दर्द है?',
  'Is there more than one place injured?': 'क्या एक से अधिक जगह चोट लगी है?',
  'About how long has it been bleeding?': 'लगभग कब से खून बह रहा है?',
  'Have you been able to apply pressure to it?': 'क्या आप उस पर दबाव डाल पाए हैं?',

  // burns
  'What caused the burn — fire, hot liquid, chemical, or electricity?': 'जलने का कारण क्या था — आग, गर्म तरल, रसायन, या बिजली?',
  'Roughly how large an area is affected?': 'लगभग कितनी बड़ी जगह प्रभावित है?',
  'Is there blistering or broken skin?': 'क्या फफोले या टूटी हुई त्वचा है?',

  // vomiting / diarrhea
  'How long have you been vomiting?': 'आपको कब से उल्टी हो रही है?',
  'About how many times so far?': 'अब तक लगभग कितनी बार?',
  'Any blood in the vomit?': 'क्या उल्टी में कोई खून है?',
  'Are you able to keep any fluids down?': 'क्या आप कोई तरल पदार्थ पचा पा रहे हैं?',
  'Any pain in your stomach?': 'क्या आपके पेट में दर्द है?',
  'Any fever or loose motions along with this?': 'क्या इसके साथ बुखार या दस्त हैं?',
  'About how many times a day?': 'दिन में लगभग कितनी बार?',
  'Any blood in your stools?': 'क्या आपके मल में खून है?',
  'Any vomiting or fever along with this?': 'क्या इसके साथ उल्टी या बुखार है?',

  // urinary
  'Is there any burning or pain when you urinate?': 'क्या पेशाब करते समय कोई जलन या दर्द है?',
  'Are you urinating more often, or feeling urgency?': 'क्या आप अधिक बार पेशाब कर रहे हैं, या तुरंत जाने की ज़रूरत महसूस हो रही है?',
  'Any blood in your urine?': 'क्या आपके पेशाब में खून है?',
  'Any pain in your back or side?': 'क्या आपकी पीठ या बगल में दर्द है?',

  // mental / self-harm
  'Are you safe right now, and is anyone with you?': 'क्या आप अभी सुरक्षित हैं, और क्या कोई आपके साथ है?',
  'Would you like us to bring someone to sit with you now?': 'क्या आप चाहेंगे कि हम अभी किसी को आपके साथ बैठने के लिए बुलाएँ?',
  'Have you done anything to hurt yourself in the last few hours?': 'क्या आपने पिछले कुछ घंटों में खुद को नुकसान पहुँचाने के लिए कुछ किया है?',
  'What did you take or do?': 'आपने क्या लिया या किया?',
  'About how long ago was that?': 'लगभग कितना समय पहले?',
  'Can you tell me a little about how you are feeling right now?': 'क्या आप मुझे थोड़ा बता सकते हैं कि आप अभी कैसा महसूस कर रहे हैं?',
  'Are you being seen by a doctor or counsellor for this already?': 'क्या इसके लिए आप पहले से किसी डॉक्टर या काउंसलर के पास जा रहे हैं?',

  // diabetic
  'Have you measured your sugar recently, and what was the number?': 'क्या आपने हाल ही में अपनी शुगर मापी है, और क्या नंबर था?',
  'Are you on insulin, or any tablets for sugar?': 'क्या आप इंसुलिन, या शुगर की कोई गोली ले रहे हैं?',
  'Did you miss a meal, or take an extra dose today?': 'क्या आपने आज कोई भोजन छोड़ा, या अतिरिक्त खुराक ली?',
  'How are they feeling now -- weak, sweaty, confused, or drowsy?': 'वे अभी कैसा महसूस कर रहे हैं — कमज़ोर, पसीने में, भ्रमित, या नींद जैसा?',
  'Are they able to answer you normally?': 'क्या वे आपको सामान्य रूप से जवाब दे पा रहे हैं?',
  'Any vomiting, deep breathing, or fruity smell on the breath?': 'क्या कोई उल्टी, गहरी साँस, या साँस में फल जैसी गंध है?',

  // stroke / neuro
  'Exactly when did this start?': 'यह ठीक कब शुरू हुआ?',
  'Which side is affected?': 'कौन सा पक्ष प्रभावित है?',
  'Any trouble speaking or understanding speech?': 'क्या बोलने या बात समझने में कोई परेशानी है?',
  'Does one side of the face look different?': 'क्या चेहरे का एक पक्ष अलग दिख रहा है?',

  // seizure / choking / poisoning
  'Can you describe exactly what happened?': 'क्या आप बता सकते हैं कि ठीक-ठीक क्या हुआ?',
  'About how long did it last?': 'यह लगभग कितनी देर तक रहा?',
  'Are they responding normally now?': 'क्या वे अभी सामान्य रूप से प्रतिक्रिया दे रहे हैं?',
  'Has anything like this happened before?': 'क्या पहले कभी ऐसा कुछ हुआ है?',
  'What got stuck, or what did they swallow, and when?': 'क्या फँसा, या उन्होंने क्या निगला, और कब?',
  'Can they breathe or make any sound right now?': 'क्या वे अभी साँस ले पा रहे हैं या कोई आवाज़ निकाल पा रहे हैं?',
  'Are they able to cough or speak at all?': 'क्या वे बिल्कुल भी खाँस या बोल पा रहे हैं?',
  'What was taken or swallowed, or what bit them?': 'क्या लिया या निगला गया, या किसने काटा?',
  'How long ago did this happen?': 'यह कितना समय पहले हुआ?',
  'Any symptoms since then, like vomiting, dizziness, or swelling?': 'तब से कोई लक्षण, जैसे उल्टी, चक्कर, या सूजन?',

  // pregnancy / bleeding
  'How many weeks pregnant are you, if known?': 'अगर पता हो, तो आप कितने सप्ताह की गर्भवती हैं?',
  'How often are the contractions coming?': 'संकुचन कितनी बार आ रहे हैं?',
  'Has your water broken, or any fluid leakage?': 'क्या आपकी पानी की थैली फट गई है, या कोई तरल रिस रहा है?',
  'Any bleeding?': 'क्या कोई खून बह रहा है?',
  'Have you felt the baby moving?': 'क्या आपने बच्चे को हिलते हुए महसूस किया है?',
  'When did the bleeding start?': 'खून बहना कब शुरू हुआ?',
  'How heavy is the bleeding?': 'खून कितना ज़्यादा बह रहा है?',
  'Is there any chance you could be pregnant?': 'क्या ऐसी कोई संभावना है कि आप गर्भवती हो सकती हैं?',
  'Any pain along with the bleeding?': 'क्या खून के साथ कोई दर्द भी है?',
};

/**
 * Return the Hindi version of a prompt when we have a confirmed
 * translation for it; otherwise return the English original. Never guess.
 */
export function translatePrompt(englishPrompt: string, lang: 'en' | 'hi'): string {
  if (lang !== 'hi') return englishPrompt;
  return HI[englishPrompt.trim()] ?? englishPrompt;
}

export function hasHindiTranslation(englishPrompt: string): boolean {
  return englishPrompt.trim() in HI;
}
