/**
 * Spoken-number parsing for English and Hindi.
 *
 * The intake tree has two numeric kinds and they are NOT the same problem:
 *
 *  - `scale_0_10` (pain) has ten legal answers, and anything else is a
 *    mis-hear that must be rejected.
 *  - `number` (age) has a hundred-plus legal answers, and the patient will
 *    say them as words at least as often as digits.
 *
 * Both used to run through the same 0–10 matcher, so an age answered by
 * voice only ever worked for patients aged ten or under. Everything above
 * that silently matched nothing and fell through to the "I didn't catch
 * that" path — the number was never wrong, it was simply never heard.
 *
 * Hindi is the reason this is a table rather than an algorithm. English
 * composes ("seventy" + "two"), but Hindi 1–100 is almost entirely
 * irregular — 72 is बहत्तर, not "सत्तर दो" — so each value needs its own
 * entry. Both the Devanagari and the common romanisation are listed,
 * because Chrome's recogniser returns Devanagari for hi-IN and romanised
 * Hindi for en-IN, and patients switch between the two mid-sentence.
 */

export const DEVANAGARI_DIGITS = '०१२३४५६७८९';

/** Rewrites Devanagari digits (७२) to ASCII (72). */
export function asciiDigits(text: string): string {
  return text.replace(/[०-९]/g, (d) => String(DEVANAGARI_DIGITS.indexOf(d)));
}

// ---------------------------------------------------------------------------
// English
// ---------------------------------------------------------------------------

export const EN_UNITS: Record<string, number> = {
  zero: 0, oh: 0, nil: 0,
  one: 1, two: 2, three: 3, four: 4, five: 5,
  six: 6, seven: 7, eight: 8, nine: 9, ten: 10,
  eleven: 11, twelve: 12, thirteen: 13, fourteen: 14, fifteen: 15,
  sixteen: 16, seventeen: 17, eighteen: 18, nineteen: 19,
};

export const EN_TENS: Record<string, number> = {
  twenty: 20, thirty: 30, forty: 40, fourty: 40, fifty: 50,
  sixty: 60, seventy: 70, eighty: 80, ninety: 90,
};

// ---------------------------------------------------------------------------
// Hindi — Devanagari and romanised, 0 to 100
// ---------------------------------------------------------------------------

/** value -> every spoken form for it. Order within a row does not matter;
 *  the matcher always prefers the LONGEST form that appears, so "इक्कीस"
 *  (21) is never shadowed by "एक" (1). */
const HI_ROWS: [number, string[]][] = [
  [0, ['शून्य', 'shunya', 'sunya']],
  [1, ['एक', 'ek', 'aik']],
  [2, ['दो', 'do']],
  [3, ['तीन', 'teen', 'tin']],
  [4, ['चार', 'char', 'chaar']],
  [5, ['पांच', 'पाँच', 'paanch', 'panch']],
  [6, ['छह', 'छः', 'chhah', 'chhe', 'che']],
  [7, ['सात', 'saat', 'sat']],
  [8, ['आठ', 'aath', 'ath']],
  [9, ['नौ', 'nau', 'no']],
  [10, ['दस', 'das', 'dus']],
  [11, ['ग्यारह', 'gyarah', 'gyara']],
  [12, ['बारह', 'barah', 'bara']],
  [13, ['तेरह', 'terah', 'tera']],
  [14, ['चौदह', 'chaudah', 'chauda']],
  [15, ['पंद्रह', 'पन्द्रह', 'pandrah', 'pandra']],
  [16, ['सोलह', 'solah', 'sola']],
  [17, ['सत्रह', 'satrah', 'satra']],
  [18, ['अठारह', 'atharah', 'athara']],
  [19, ['उन्नीस', 'unnis', 'unis']],
  [20, ['बीस', 'bees', 'bis']],
  [21, ['इक्कीस', 'ikkis', 'ikis']],
  [22, ['बाईस', 'bais', 'baees']],
  [23, ['तेईस', 'teis', 'teees']],
  [24, ['चौबीस', 'chaubis', 'chaubees']],
  [25, ['पच्चीस', 'pachchis', 'pachis']],
  [26, ['छब्बीस', 'chhabbis', 'chabbis']],
  [27, ['सत्ताईस', 'sattais', 'satais']],
  [28, ['अट्ठाईस', 'atthais', 'athais']],
  [29, ['उनतीस', 'untis', 'unatis']],
  [30, ['तीस', 'tees', 'tis']],
  [31, ['इकतीस', 'ikatis', 'iktis']],
  [32, ['बत्तीस', 'battis', 'batis']],
  [33, ['तैंतीस', 'taintis', 'tentis']],
  [34, ['चौंतीस', 'chauntis', 'chautis']],
  [35, ['पैंतीस', 'paintis', 'pentis']],
  [36, ['छत्तीस', 'chhattis', 'chatis']],
  [37, ['सैंतीस', 'saintis', 'sentis']],
  [38, ['अड़तीस', 'अडतीस', 'adtis', 'artis']],
  [39, ['उनतालीस', 'unchalis', 'untalis']],
  [40, ['चालीस', 'chalis', 'chaalis']],
  [41, ['इकतालीस', 'ikatalis', 'iktalis']],
  [42, ['बयालीस', 'bayalis', 'bayalees']],
  [43, ['तैंतालीस', 'taintalis', 'tentalis']],
  [44, ['चवालीस', 'chavalis', 'chauvalis']],
  [45, ['पैंतालीस', 'paintalis', 'pentalis']],
  [46, ['छियालीस', 'chhiyalis', 'chiyalis']],
  [47, ['सैंतालीस', 'saintalis', 'sentalis']],
  [48, ['अड़तालीस', 'अडतालीस', 'adtalis', 'artalis']],
  [49, ['उनचास', 'unchas', 'unachas']],
  [50, ['पचास', 'pachas', 'pachaas']],
  [51, ['इक्यावन', 'ikyavan', 'ikyawan']],
  [52, ['बावन', 'bavan', 'bawan']],
  [53, ['तिरेपन', 'tirepan', 'trepan']],
  [54, ['चौवन', 'chauvan', 'chauwan']],
  [55, ['पचपन', 'pachpan']],
  [56, ['छप्पन', 'chhappan', 'chappan']],
  [57, ['सत्तावन', 'sattavan', 'satavan']],
  [58, ['अट्ठावन', 'atthavan', 'athavan']],
  [59, ['उनसठ', 'unsath', 'unasath']],
  [60, ['साठ', 'sath', 'saath']],
  [61, ['इकसठ', 'iksath', 'ikasath']],
  [62, ['बासठ', 'basath', 'baasath']],
  [63, ['तिरेसठ', 'tiresath', 'tresath']],
  [64, ['चौंसठ', 'chausath', 'chaunsath']],
  [65, ['पैंसठ', 'painsath', 'pensath']],
  [66, ['छियासठ', 'chhiyasath', 'chiyasath']],
  [67, ['सड़सठ', 'सडसठ', 'sarsath', 'sadsath']],
  [68, ['अड़सठ', 'अडसठ', 'arsath', 'adsath']],
  [69, ['उनहत्तर', 'unhattar', 'unahattar']],
  [70, ['सत्तर', 'sattar', 'satar']],
  [71, ['इकहत्तर', 'ikhattar', 'ikahattar']],
  [72, ['बहत्तर', 'bahattar', 'bahatar']],
  [73, ['तिहत्तर', 'tihattar', 'tihatar']],
  [74, ['चौहत्तर', 'chauhattar', 'chauhatar']],
  [75, ['पचहत्तर', 'pachhattar', 'pachahattar']],
  [76, ['छिहत्तर', 'chhihattar', 'chihattar']],
  [77, ['सतहत्तर', 'satattar', 'satahattar']],
  [78, ['अठहत्तर', 'athhattar', 'athahattar']],
  [79, ['उन्यासी', 'unyasi', 'unasi']],
  [80, ['अस्सी', 'assi', 'asi']],
  [81, ['इक्यासी', 'ikyasi', 'ikyaasi']],
  [82, ['बयासी', 'bayasi', 'bayaasi']],
  [83, ['तिरासी', 'tirasi', 'tiraasi']],
  [84, ['चौरासी', 'chaurasi', 'chauraasi']],
  [85, ['पचासी', 'pachasi', 'pachaasi']],
  [86, ['छियासी', 'chhiyasi', 'chiyasi']],
  [87, ['सतासी', 'satasi', 'sataasi']],
  [88, ['अठासी', 'athasi', 'athaasi']],
  [89, ['नवासी', 'navasi', 'nawasi']],
  [90, ['नब्बे', 'nabbe', 'nabe']],
  [91, ['इक्यानवे', 'ikyanave', 'ikyanve']],
  [92, ['बानवे', 'banave', 'banve']],
  [93, ['तिरानवे', 'tiranave', 'tiranve']],
  [94, ['चौरानवे', 'chauranave', 'chauranve']],
  [95, ['पंचानवे', 'panchanave', 'panchanve']],
  [96, ['छियानवे', 'chhiyanave', 'chiyanave']],
  [97, ['सत्तानवे', 'sattanave', 'satanve']],
  [98, ['अट्ठानवे', 'atthanave', 'athanve']],
  [99, ['निन्यानवे', 'ninyanave', 'ninyanve']],
  [100, ['सौ', 'sau', 'ek sau']],
];

const DEVANAGARI = /[ऀ-ॿ]/;

/** Every Hindi form, longest first — so a 21 is read as इक्कीस and never
 *  as the एक hiding inside it. */
const ALL_HI_FORMS: [string, number][] = HI_ROWS
  .flatMap(([value, forms]) => forms.map((f) => [f, value] as [string, number]))
  .sort((a, b) => b[0].length - a[0].length);

/**
 * Devanagari forms are unambiguous — no English word is spelled in
 * Devanagari, so these are safe to match in any language mode.
 */
export const HI_FORMS_SCRIPT: [string, number][] =
  ALL_HI_FORMS.filter(([form]) => DEVANAGARI.test(form));

/**
 * Romanised forms that are ALSO ordinary English words.
 *
 * "do" is 2, "no" is 9, "sat" and "tin" and "char" and "teen" are 7, 3, 4
 * and 3. Matching these in English mode turned "I do not know" into the
 * age 2 — which resolves the *infant* stratum and rewrites every vital
 * threshold downstream. A patient saying they don't know their age must
 * produce no answer, not a toddler.
 *
 * These are gated to Hindi mode. Every OTHER romanisation — bahattar,
 * pachas, saat, chaar — stays available in both modes, because English
 * and Hindi are routinely code-mixed in one sentence and a blanket gate
 * would break "I am bahattar" for no safety benefit.
 */
const ROMAN_COLLIDES_WITH_ENGLISH = new Set([
  'do', 'no', 'che', 'sat', 'tin', 'teen', 'char', 'so', 'ha', 'na', 'sola',
]);

const ROMAN_FORMS = ALL_HI_FORMS.filter(([form]) => !DEVANAGARI.test(form));

/** Romanised Hindi safe to match in any language mode. */
export const HI_FORMS_ROMAN_SAFE: [string, number][] =
  ROMAN_FORMS.filter(([form]) => !ROMAN_COLLIDES_WITH_ENGLISH.has(form));

/** Romanised Hindi that only resolves when the patient chose Hindi. */
export const HI_FORMS_ROMAN_AMBIGUOUS: [string, number][] =
  ROMAN_FORMS.filter(([form]) => ROMAN_COLLIDES_WITH_ENGLISH.has(form));
