# RKR — Risk Keywords List

Full hardcoded keyword list for the Risk Keywords Regex module.
Total: ~145 keywords across 9 categories, English + Polish.

Each keyword has:
- **phrase** — the literal term
- **category** — risk category it belongs to
- **weight** — contribution to risk_score (0.0–1.0)
- **lang** — `en` / `pl`

---

## `terrorism_financing` — weight 1.0

| Phrase | Lang |
|---|---|
| terrorism financing | en |
| terrorist financing | en |
| financing of terrorism | en |
| finansowanie terroryzmu | pl |
| finansowanie działalności terrorystycznej | pl |
| terrorist organization | en |
| organizacja terrorystyczna | pl |
| jihadist | en |
| foreign fighter | en |

---

## `sanctions` — weight 0.95

| Phrase | Lang |
|---|---|
| OFAC | en |
| SDN list | en |
| specially designated national | en |
| EU sanctions | en |
| UN sanctions | en |
| sanctions list | en |
| sanctioned entity | en |
| sankcja | pl |
| sankcje | pl |
| lista sankcji | pl |
| objęty sankcjami | pl |
| blacklist | en |
| czarna lista | pl |
| asset freeze | en |
| zamrożenie aktywów | pl |
| travel ban | en |
| arms embargo | en |
| embargo | en/pl |

---

## `money_laundering` — weight 0.9

| Phrase | Lang |
|---|---|
| money laundering | en |
| pranie pieniędzy | pl |
| pranie brudnych pieniędzy | pl |
| laundering proceeds | en |
| structuring | en |
| smurfing | en |
| layering | en |
| placement stage | en |
| integration of funds | en |
| suspicious transaction | en |
| podejrzana transakcja | pl |
| suspicious activity report | en |
| SAR filing | en |
| shell account | en |
| nominee account | en |
| konto słupa | pl |
| illegal proceeds | en |
| nielegalne środki | pl |
| origin of funds | en |
| pochodzenie środków | pl |
| cash smuggling | en |
| trade-based money laundering | en |
| TBML | en |
| virtual asset laundering | en |

---

## `fraud` — weight 0.85

| Phrase | Lang |
|---|---|
| fraud | en |
| oszustwo | pl |
| fraudulent | en |
| fraudulent scheme | en |
| embezzlement | en |
| sprzeniewierzenie | pl |
| misappropriation | en |
| przywłaszczenie | pl |
| ponzi scheme | en |
| pyramid scheme | en |
| schemat Ponziego | pl |
| piramida finansowa | pl |
| falsification | en |
| fałszowanie | pl |
| forgery | en |
| fałszowanie dokumentów | pl |
| accounting fraud | en |
| manipulacja księgowością | pl |
| invoice fraud | en |
| faktura fałszywa | pl |
| identity theft | en |
| kradzież tożsamości | pl |
| securities fraud | en |
| insider trading | en |
| market manipulation | en |
| manipulacja rynkiem | pl |

---

## `corruption` — weight 0.8

| Phrase | Lang |
|---|---|
| bribery | en |
| korupcja | pl |
| łapówka | pl |
| kickback | en |
| łapownictwo | pl |
| nepotism | en |
| nepotyzm | pl |
| conflict of interest | en |
| konflikt interesów | pl |
| abuse of power | en |
| nadużycie władzy | pl |
| public official corruption | en |
| korupcja urzędnicza | pl |
| political corruption | en |
| korupcja polityczna | pl |
| CBA | pl |
| bribe | en |
| przekupstwo | pl |
| graft | en |

---

## `regulatory_action` — weight 0.75

| Phrase | Lang |
|---|---|
| KNF | pl |
| SEC investigation | en |
| FCA action | en |
| regulatory fine | en |
| enforcement action | en |
| kara finansowa | pl |
| kara administracyjna | pl |
| regulatory investigation | en |
| postępowanie administracyjne | pl |
| postępowanie wyjaśniające | pl |
| license revocation | en |
| cofnięcie licencji | pl |
| suspension of operations | en |
| zawieszenie działalności | pl |
| AML violation | en |
| naruszenie AML | pl |
| compliance breach | en |
| naruszenie przepisów | pl |
| regulatory sanction | en |
| NBP | pl |
| UOKiK | pl |

---

## `tax_evasion` — weight 0.7

| Phrase | Lang |
|---|---|
| tax evasion | en |
| uchylanie się od podatków | pl |
| tax fraud | en |
| oszustwo podatkowe | pl |
| offshore account | en |
| konto offshore | pl |
| shell company | en |
| spółka fasadowa | pl |
| spółka przykrywka | pl |
| tax haven | en |
| raj podatkowy | pl |
| hidden assets | en |
| ukryte aktywa | pl |
| undeclared income | en |
| niezgłoszony dochód | pl |
| VAT fraud | en/pl |
| karuzela VAT | pl |
| VAT carousel | en |
| transfer pricing abuse | en |
| agresywna optymalizacja podatkowa | pl |

---

## `cybercrime` — weight 0.65

| Phrase | Lang |
|---|---|
| ransomware | en |
| phishing | en |
| cyberattack | en |
| atak cybernetyczny | pl |
| data breach | en |
| wyciek danych | pl |
| hacking | en |
| włamanie do systemu | pl |
| malware | en |
| cryptocurrency theft | en |
| kradzież kryptowalut | pl |
| dark web | en |
| darknet | en |

---

## `bankruptcy` — weight 0.6

| Phrase | Lang |
|---|---|
| bankruptcy | en |
| upadłość | pl |
| insolvency | en |
| niewypłacalność | pl |
| liquidation | en |
| likwidacja | pl |
| receivership | en |
| zarząd komisaryczny | pl |
| debt restructuring | en |
| restrukturyzacja długu | pl |
| creditor claims | en |
| wierzytelności | pl |
| default | en |
| niewypełnienie zobowiązań | pl |

---

## Notes

- All patterns compiled with `re.IGNORECASE` and `re.UNICODE`
- Multi-word phrases use `\s+` between words to handle extra whitespace
- Polish inflection handled via partial stem matching where needed (e.g. `sankcj` catches sankcja/sankcje/sankcji)
- Acronyms (KNF, OFAC, SAR, TBML) matched as exact uppercase tokens
- `default` in `bankruptcy` category is matched only with surrounding financial context words to avoid false positives
