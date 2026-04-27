from typing import TypedDict


class KeywordDef(TypedDict):
    phrase: str
    pattern: str
    category: str
    weight: float
    lang: str


RISK_KEYWORDS: list[KeywordDef] = [
    # -------------------------------------------------------------------------
    # terrorism_financing — weight 1.0
    # -------------------------------------------------------------------------
    {"phrase": "terrorism financing",                         "pattern": r"\bterrorism[\s\-]financing\b",                           "category": "terrorism_financing", "weight": 1.0, "lang": "en"},
    {"phrase": "terrorist financing",                         "pattern": r"\bterrorist[\s\-]financing\b",                            "category": "terrorism_financing", "weight": 1.0, "lang": "en"},
    {"phrase": "financing of terrorism",                      "pattern": r"\bfinancing\s+of\s+terrorism\b",                          "category": "terrorism_financing", "weight": 1.0, "lang": "en"},
    {"phrase": "finansowanie terroryzmu",                     "pattern": r"\bfinansowanie\s+terroryzmu\b",                           "category": "terrorism_financing", "weight": 1.0, "lang": "pl"},
    {"phrase": "finansowanie działalności terrorystycznej",   "pattern": r"\bfinansowanie\s+działalności\s+terrorystycznej\b", "category": "terrorism_financing", "weight": 1.0, "lang": "pl"},
    {"phrase": "terrorist organization",                      "pattern": r"\bterrorist\s+organi[sz]ation\b",                         "category": "terrorism_financing", "weight": 1.0, "lang": "en"},
    {"phrase": "organizacja terrorystyczna",                  "pattern": r"\borganizacja\s+terrorystyczna\b",                        "category": "terrorism_financing", "weight": 1.0, "lang": "pl"},
    {"phrase": "jihadist",                                    "pattern": r"\bjihadist\b",                                            "category": "terrorism_financing", "weight": 1.0, "lang": "en"},
    {"phrase": "foreign fighter",                             "pattern": r"\bforeign\s+fighter\b",                                   "category": "terrorism_financing", "weight": 1.0, "lang": "en"},

    # -------------------------------------------------------------------------
    # sanctions — weight 0.95
    # -------------------------------------------------------------------------
    {"phrase": "OFAC",                        "pattern": r"\bOFAC\b",                                        "category": "sanctions", "weight": 0.95, "lang": "en"},
    {"phrase": "SDN list",                    "pattern": r"\bSDN\s+list\b",                                  "category": "sanctions", "weight": 0.95, "lang": "en"},
    {"phrase": "specially designated national","pattern": r"\bspecially\s+designated\s+national\b",          "category": "sanctions", "weight": 0.95, "lang": "en"},
    {"phrase": "EU sanctions",                "pattern": r"\bEU\s+sanctions\b",                              "category": "sanctions", "weight": 0.95, "lang": "en"},
    {"phrase": "UN sanctions",                "pattern": r"\bUN\s+sanctions\b",                              "category": "sanctions", "weight": 0.95, "lang": "en"},
    {"phrase": "sanctions list",              "pattern": r"\bsanctions\s+list\b",                            "category": "sanctions", "weight": 0.95, "lang": "en"},
    {"phrase": "sanctioned entity",           "pattern": r"\bsanctioned\s+entit(?:y|ies)\b",                 "category": "sanctions", "weight": 0.95, "lang": "en"},
    {"phrase": "sankcja",                     "pattern": r"\bsankcj[aięą]\b",                                "category": "sanctions", "weight": 0.95, "lang": "pl"},
    {"phrase": "lista sankcji",               "pattern": r"\blista\s+sankcji\b",                             "category": "sanctions", "weight": 0.95, "lang": "pl"},
    {"phrase": "objęty sankcjami",            "pattern": r"\bobjęty\s+sankcjami\b",                          "category": "sanctions", "weight": 0.95, "lang": "pl"},
    {"phrase": "blacklist",                   "pattern": r"\bblacklist(?:ed)?\b",                            "category": "sanctions", "weight": 0.95, "lang": "en"},
    {"phrase": "czarna lista",                "pattern": r"\bczarna\s+lista\b",                              "category": "sanctions", "weight": 0.95, "lang": "pl"},
    {"phrase": "asset freeze",                "pattern": r"\basset\s+freeze\b",                              "category": "sanctions", "weight": 0.95, "lang": "en"},
    {"phrase": "zamrożenie aktywów",          "pattern": r"\bzamrożenie\s+aktywów\b",              "category": "sanctions", "weight": 0.95, "lang": "pl"},
    {"phrase": "travel ban",                  "pattern": r"\btravel\s+ban\b",                                "category": "sanctions", "weight": 0.95, "lang": "en"},
    {"phrase": "arms embargo",                "pattern": r"\barms\s+embargo\b",                              "category": "sanctions", "weight": 0.95, "lang": "en"},
    {"phrase": "embargo",                     "pattern": r"\bembargo\b",                                     "category": "sanctions", "weight": 0.95, "lang": "en"},

    # -------------------------------------------------------------------------
    # money_laundering — weight 0.9
    # -------------------------------------------------------------------------
    {"phrase": "money laundering",            "pattern": r"\bmoney[\s\-]laundering\b",                       "category": "money_laundering", "weight": 0.9, "lang": "en"},
    {"phrase": "pranie pieniędzy",            "pattern": r"\bpranie\s+pieni[eę]dzy\b",                       "category": "money_laundering", "weight": 0.9, "lang": "pl"},
    {"phrase": "pranie brudnych pieniędzy",   "pattern": r"\bpranie\s+brudnych\s+pieni[eę]dzy\b",            "category": "money_laundering", "weight": 0.9, "lang": "pl"},
    {"phrase": "laundering proceeds",         "pattern": r"\blaundering\s+proceeds\b",                       "category": "money_laundering", "weight": 0.9, "lang": "en"},
    {"phrase": "structuring",                 "pattern": r"\bstructuring\b",                                 "category": "money_laundering", "weight": 0.9, "lang": "en"},
    {"phrase": "smurfing",                    "pattern": r"\bsmurfing\b",                                    "category": "money_laundering", "weight": 0.9, "lang": "en"},
    {"phrase": "layering",                    "pattern": r"\blayering\b",                                    "category": "money_laundering", "weight": 0.9, "lang": "en"},
    {"phrase": "placement stage",             "pattern": r"\bplacement\s+stage\b",                           "category": "money_laundering", "weight": 0.9, "lang": "en"},
    {"phrase": "integration of funds",        "pattern": r"\bintegration\s+of\s+funds\b",                    "category": "money_laundering", "weight": 0.9, "lang": "en"},
    {"phrase": "suspicious transaction",      "pattern": r"\bsuspicious\s+transactions?\b",                  "category": "money_laundering", "weight": 0.9, "lang": "en"},
    {"phrase": "podejrzana transakcja",       "pattern": r"\bpodejrzana\s+transakcj[aią]\b",                 "category": "money_laundering", "weight": 0.9, "lang": "pl"},
    {"phrase": "suspicious activity report",  "pattern": r"\bsuspicious\s+activity\s+report\b",              "category": "money_laundering", "weight": 0.9, "lang": "en"},
    {"phrase": "SAR filing",                  "pattern": r"\bSAR\s+filing\b",                                "category": "money_laundering", "weight": 0.9, "lang": "en"},
    {"phrase": "shell account",               "pattern": r"\bshell\s+account\b",                             "category": "money_laundering", "weight": 0.9, "lang": "en"},
    {"phrase": "nominee account",             "pattern": r"\bnominee\s+account\b",                           "category": "money_laundering", "weight": 0.9, "lang": "en"},
    {"phrase": "konto słupa",                 "pattern": r"\bkonto\s+słupa\b",                          "category": "money_laundering", "weight": 0.9, "lang": "pl"},
    {"phrase": "illegal proceeds",            "pattern": r"\billegal\s+proceeds\b",                          "category": "money_laundering", "weight": 0.9, "lang": "en"},
    {"phrase": "nielegalne środki",           "pattern": r"\bnielegalne\s+środki\b",                    "category": "money_laundering", "weight": 0.9, "lang": "pl"},
    {"phrase": "origin of funds",             "pattern": r"\borigin\s+of\s+funds\b",                         "category": "money_laundering", "weight": 0.9, "lang": "en"},
    {"phrase": "cash smuggling",              "pattern": r"\bcash\s+smuggling\b",                            "category": "money_laundering", "weight": 0.9, "lang": "en"},
    {"phrase": "trade-based money laundering","pattern": r"\btrade[\s\-]based\s+money[\s\-]laundering\b",    "category": "money_laundering", "weight": 0.9, "lang": "en"},
    {"phrase": "TBML",                        "pattern": r"\bTBML\b",                                        "category": "money_laundering", "weight": 0.9, "lang": "en"},
    {"phrase": "virtual asset laundering",    "pattern": r"\bvirtual\s+asset\s+laundering\b",                "category": "money_laundering", "weight": 0.9, "lang": "en"},

    # -------------------------------------------------------------------------
    # fraud — weight 0.85
    # -------------------------------------------------------------------------
    {"phrase": "fraud",                       "pattern": r"\bfraud\b",                                       "category": "fraud", "weight": 0.85, "lang": "en"},
    {"phrase": "oszustwo",                    "pattern": r"\boszustwo\b",                                    "category": "fraud", "weight": 0.85, "lang": "pl"},
    {"phrase": "fraudulent scheme",           "pattern": r"\bfraudulent\s+scheme\b",                         "category": "fraud", "weight": 0.85, "lang": "en"},
    {"phrase": "embezzlement",                "pattern": r"\bembezzlement\b",                                "category": "fraud", "weight": 0.85, "lang": "en"},
    {"phrase": "sprzeniewierzenie",           "pattern": r"\bsprzeniewierzenie\b",                           "category": "fraud", "weight": 0.85, "lang": "pl"},
    {"phrase": "misappropriation",            "pattern": r"\bmisappropriation\b",                            "category": "fraud", "weight": 0.85, "lang": "en"},
    {"phrase": "przywłaszczenie",             "pattern": r"\bprzywłaszczenie\b",                        "category": "fraud", "weight": 0.85, "lang": "pl"},
    {"phrase": "ponzi scheme",                "pattern": r"\bponzi\s+scheme\b",                              "category": "fraud", "weight": 0.85, "lang": "en"},
    {"phrase": "pyramid scheme",              "pattern": r"\bpyramid\s+scheme\b",                            "category": "fraud", "weight": 0.85, "lang": "en"},
    {"phrase": "schemat Ponziego",            "pattern": r"\bschemat\s+Ponziego\b",                          "category": "fraud", "weight": 0.85, "lang": "pl"},
    {"phrase": "piramida finansowa",          "pattern": r"\bpiramida\s+finansowa\b",                        "category": "fraud", "weight": 0.85, "lang": "pl"},
    {"phrase": "forgery",                     "pattern": r"\bforger(?:y|ies)\b",                             "category": "fraud", "weight": 0.85, "lang": "en"},
    {"phrase": "fałszowanie dokumentów",      "pattern": r"\bfałszowanie\s+dokumentów\b",          "category": "fraud", "weight": 0.85, "lang": "pl"},
    {"phrase": "accounting fraud",            "pattern": r"\baccounting\s+fraud\b",                          "category": "fraud", "weight": 0.85, "lang": "en"},
    {"phrase": "invoice fraud",               "pattern": r"\binvoice\s+fraud\b",                             "category": "fraud", "weight": 0.85, "lang": "en"},
    {"phrase": "faktura fałszywa",            "pattern": r"\bfaktura\s+fałszywa\b",                     "category": "fraud", "weight": 0.85, "lang": "pl"},
    {"phrase": "identity theft",              "pattern": r"\bidentity\s+theft\b",                            "category": "fraud", "weight": 0.85, "lang": "en"},
    {"phrase": "kradzież tożsamości",         "pattern": r"\bkradzież\s+tożsamości\b",        "category": "fraud", "weight": 0.85, "lang": "pl"},
    {"phrase": "securities fraud",            "pattern": r"\bsecurities\s+fraud\b",                          "category": "fraud", "weight": 0.85, "lang": "en"},
    {"phrase": "insider trading",             "pattern": r"\binsider\s+trading\b",                           "category": "fraud", "weight": 0.85, "lang": "en"},
    {"phrase": "market manipulation",         "pattern": r"\bmarket\s+manipulation\b",                       "category": "fraud", "weight": 0.85, "lang": "en"},
    {"phrase": "manipulacja rynkiem",         "pattern": r"\bmanipulacja\s+rynkiem\b",                       "category": "fraud", "weight": 0.85, "lang": "pl"},

    # -------------------------------------------------------------------------
    # corruption — weight 0.8
    # -------------------------------------------------------------------------
    {"phrase": "bribery",                     "pattern": r"\bbribery\b",                                     "category": "corruption", "weight": 0.8, "lang": "en"},
    {"phrase": "korupcja",                    "pattern": r"\bkorupcj[aią]\b",                                "category": "corruption", "weight": 0.8, "lang": "pl"},
    {"phrase": "łapówka",                     "pattern": r"\błapówk[aią]\b",                       "category": "corruption", "weight": 0.8, "lang": "pl"},
    {"phrase": "kickback",                    "pattern": r"\bkickback\b",                                    "category": "corruption", "weight": 0.8, "lang": "en"},
    {"phrase": "łapownictwo",                 "pattern": r"\błapownictwo\b",                            "category": "corruption", "weight": 0.8, "lang": "pl"},
    {"phrase": "nepotism",                    "pattern": r"\bnepotism\b",                                    "category": "corruption", "weight": 0.8, "lang": "en"},
    {"phrase": "nepotyzm",                    "pattern": r"\bnepotyzm\b",                                    "category": "corruption", "weight": 0.8, "lang": "pl"},
    {"phrase": "conflict of interest",        "pattern": r"\bconflict\s+of\s+interest\b",                    "category": "corruption", "weight": 0.8, "lang": "en"},
    {"phrase": "konflikt interesów",          "pattern": r"\bkonflikt\s+interesów\b",                   "category": "corruption", "weight": 0.8, "lang": "pl"},
    {"phrase": "abuse of power",              "pattern": r"\babuse\s+of\s+power\b",                          "category": "corruption", "weight": 0.8, "lang": "en"},
    {"phrase": "nadużycie władzy",            "pattern": r"\bnadużycie\s+władzy\b",                "category": "corruption", "weight": 0.8, "lang": "pl"},
    {"phrase": "public official corruption",  "pattern": r"\bpublic\s+official\s+corruption\b",              "category": "corruption", "weight": 0.8, "lang": "en"},
    {"phrase": "korupcja urzędnicza",         "pattern": r"\bkorupcja\s+urz[eę]dnicza\b",                   "category": "corruption", "weight": 0.8, "lang": "pl"},
    {"phrase": "korupcja polityczna",         "pattern": r"\bkorupcja\s+polityczna\b",                       "category": "corruption", "weight": 0.8, "lang": "pl"},
    {"phrase": "CBA",                         "pattern": r"\bCBA\b",                                         "category": "corruption", "weight": 0.8, "lang": "pl"},
    {"phrase": "przekupstwo",                 "pattern": r"\bprzekupstwo\b",                                 "category": "corruption", "weight": 0.8, "lang": "pl"},
    {"phrase": "graft",                       "pattern": r"\bgraft\b",                                       "category": "corruption", "weight": 0.8, "lang": "en"},

    # -------------------------------------------------------------------------
    # regulatory_action — weight 0.75
    # -------------------------------------------------------------------------
    {"phrase": "KNF",                         "pattern": r"\bKNF\b",                                         "category": "regulatory_action", "weight": 0.75, "lang": "pl"},
    {"phrase": "SEC investigation",           "pattern": r"\bSEC\s+investigation\b",                         "category": "regulatory_action", "weight": 0.75, "lang": "en"},
    {"phrase": "FCA action",                  "pattern": r"\bFCA\s+(?:action|enforcement|fine|penalty)\b",   "category": "regulatory_action", "weight": 0.75, "lang": "en"},
    {"phrase": "regulatory fine",             "pattern": r"\bregulatory\s+fine\b",                           "category": "regulatory_action", "weight": 0.75, "lang": "en"},
    {"phrase": "enforcement action",          "pattern": r"\benforcement\s+action\b",                        "category": "regulatory_action", "weight": 0.75, "lang": "en"},
    {"phrase": "kara finansowa",              "pattern": r"\bkara\s+finansowa\b",                            "category": "regulatory_action", "weight": 0.75, "lang": "pl"},
    {"phrase": "kara administracyjna",        "pattern": r"\bkara\s+administracyjna\b",                      "category": "regulatory_action", "weight": 0.75, "lang": "pl"},
    {"phrase": "regulatory investigation",    "pattern": r"\bregulatory\s+investigation\b",                  "category": "regulatory_action", "weight": 0.75, "lang": "en"},
    {"phrase": "postępowanie administracyjne","pattern": r"\bpost[eę]powanie\s+administracyjne\b",            "category": "regulatory_action", "weight": 0.75, "lang": "pl"},
    {"phrase": "postępowanie wyjaśniające",   "pattern": r"\bpost[eę]powanie\s+wyjaśniające\b",    "category": "regulatory_action", "weight": 0.75, "lang": "pl"},
    {"phrase": "license revocation",          "pattern": r"\blicen[sc]e\s+revocation\b",                     "category": "regulatory_action", "weight": 0.75, "lang": "en"},
    {"phrase": "cofnięcie licencji",          "pattern": r"\bcofni[eę]cie\s+licencji\b",                     "category": "regulatory_action", "weight": 0.75, "lang": "pl"},
    {"phrase": "suspension of operations",    "pattern": r"\bsuspension\s+of\s+operations\b",                "category": "regulatory_action", "weight": 0.75, "lang": "en"},
    {"phrase": "zawieszenie działalności",    "pattern": r"\bzawieszenie\s+działalności\b",        "category": "regulatory_action", "weight": 0.75, "lang": "pl"},
    {"phrase": "AML violation",               "pattern": r"\bAML\s+violation\b",                             "category": "regulatory_action", "weight": 0.75, "lang": "en"},
    {"phrase": "naruszenie AML",              "pattern": r"\bnaruszenie\s+AML\b",                            "category": "regulatory_action", "weight": 0.75, "lang": "pl"},
    {"phrase": "compliance breach",           "pattern": r"\bcompliance\s+breach\b",                         "category": "regulatory_action", "weight": 0.75, "lang": "en"},
    {"phrase": "naruszenie przepisów",        "pattern": r"\bnaruszenie\s+przepisów\b",                 "category": "regulatory_action", "weight": 0.75, "lang": "pl"},
    {"phrase": "NBP",                         "pattern": r"\bNBP\b",                                         "category": "regulatory_action", "weight": 0.75, "lang": "pl"},
    {"phrase": "UOKiK",                       "pattern": r"\bUOKiK\b",                                       "category": "regulatory_action", "weight": 0.75, "lang": "pl"},

    # -------------------------------------------------------------------------
    # tax_evasion — weight 0.7
    # -------------------------------------------------------------------------
    {"phrase": "tax evasion",                 "pattern": r"\btax\s+evasion\b",                               "category": "tax_evasion", "weight": 0.7, "lang": "en"},
    {"phrase": "uchylanie się od podatków",   "pattern": r"\buchylanie\s+si[eę]\s+od\s+podatków\b",    "category": "tax_evasion", "weight": 0.7, "lang": "pl"},
    {"phrase": "tax fraud",                   "pattern": r"\btax\s+fraud\b",                                 "category": "tax_evasion", "weight": 0.7, "lang": "en"},
    {"phrase": "oszustwo podatkowe",          "pattern": r"\boszustwo\s+podatkowe\b",                        "category": "tax_evasion", "weight": 0.7, "lang": "pl"},
    {"phrase": "offshore account",            "pattern": r"\boffshore\s+account\b",                          "category": "tax_evasion", "weight": 0.7, "lang": "en"},
    {"phrase": "shell company",               "pattern": r"\bshell\s+compan(?:y|ies)\b",                     "category": "tax_evasion", "weight": 0.7, "lang": "en"},
    {"phrase": "spółka fasadowa",             "pattern": r"\bspółka\s+fasadowa\b",                 "category": "tax_evasion", "weight": 0.7, "lang": "pl"},
    {"phrase": "spółka przykrywka",           "pattern": r"\bspółka\s+przykrywka\b",               "category": "tax_evasion", "weight": 0.7, "lang": "pl"},
    {"phrase": "tax haven",                   "pattern": r"\btax\s+haven\b",                                 "category": "tax_evasion", "weight": 0.7, "lang": "en"},
    {"phrase": "raj podatkowy",               "pattern": r"\braj\s+podatkowy\b",                             "category": "tax_evasion", "weight": 0.7, "lang": "pl"},
    {"phrase": "hidden assets",               "pattern": r"\bhidden\s+assets\b",                             "category": "tax_evasion", "weight": 0.7, "lang": "en"},
    {"phrase": "ukryte aktywa",               "pattern": r"\bukryte\s+aktywa\b",                             "category": "tax_evasion", "weight": 0.7, "lang": "pl"},
    {"phrase": "undeclared income",           "pattern": r"\bundeclared\s+income\b",                         "category": "tax_evasion", "weight": 0.7, "lang": "en"},
    {"phrase": "niezgłoszony dochód",         "pattern": r"\bniezgłoszony\s+dochód\b",             "category": "tax_evasion", "weight": 0.7, "lang": "pl"},
    {"phrase": "VAT fraud",                   "pattern": r"\bVAT\s+fraud\b",                                 "category": "tax_evasion", "weight": 0.7, "lang": "en"},
    {"phrase": "karuzela VAT",                "pattern": r"\bkaruzela\s+VAT\b",                              "category": "tax_evasion", "weight": 0.7, "lang": "pl"},
    {"phrase": "VAT carousel",                "pattern": r"\bVAT\s+carousel\b",                              "category": "tax_evasion", "weight": 0.7, "lang": "en"},
    {"phrase": "transfer pricing abuse",      "pattern": r"\btransfer\s+pricing\s+abuse\b",                  "category": "tax_evasion", "weight": 0.7, "lang": "en"},
    {"phrase": "agresywna optymalizacja podatkowa", "pattern": r"\bagresywna\s+optymalizacja\s+podatkowa\b", "category": "tax_evasion", "weight": 0.7, "lang": "pl"},

    # -------------------------------------------------------------------------
    # cybercrime — weight 0.65
    # -------------------------------------------------------------------------
    {"phrase": "ransomware",                  "pattern": r"\bransomware\b",                                  "category": "cybercrime", "weight": 0.65, "lang": "en"},
    {"phrase": "phishing",                    "pattern": r"\bphishing\b",                                    "category": "cybercrime", "weight": 0.65, "lang": "en"},
    {"phrase": "cyberattack",                 "pattern": r"\bcyber[\s\-]?attack\b",                          "category": "cybercrime", "weight": 0.65, "lang": "en"},
    {"phrase": "atak cybernetyczny",          "pattern": r"\batak\s+cybernetyczny\b",                        "category": "cybercrime", "weight": 0.65, "lang": "pl"},
    {"phrase": "data breach",                 "pattern": r"\bdata\s+breach\b",                               "category": "cybercrime", "weight": 0.65, "lang": "en"},
    {"phrase": "wyciek danych",               "pattern": r"\bwyciek\s+danych\b",                             "category": "cybercrime", "weight": 0.65, "lang": "pl"},
    {"phrase": "hacking",                     "pattern": r"\bhacking\b",                                     "category": "cybercrime", "weight": 0.65, "lang": "en"},
    {"phrase": "włamanie do systemu",         "pattern": r"\bwłamanie\s+do\s+systemu\b",                "category": "cybercrime", "weight": 0.65, "lang": "pl"},
    {"phrase": "malware",                     "pattern": r"\bmalware\b",                                     "category": "cybercrime", "weight": 0.65, "lang": "en"},
    {"phrase": "cryptocurrency theft",        "pattern": r"\bcryptocurrenc(?:y|ies)\s+theft\b",              "category": "cybercrime", "weight": 0.65, "lang": "en"},
    {"phrase": "kradzież kryptowalut",        "pattern": r"\bkradzież\s+kryptowalut\b",                 "category": "cybercrime", "weight": 0.65, "lang": "pl"},
    {"phrase": "dark web",                    "pattern": r"\bdark\s+web\b",                                  "category": "cybercrime", "weight": 0.65, "lang": "en"},
    {"phrase": "darknet",                     "pattern": r"\bdarknet\b",                                     "category": "cybercrime", "weight": 0.65, "lang": "en"},

    # -------------------------------------------------------------------------
    # bankruptcy — weight 0.6
    # -------------------------------------------------------------------------
    {"phrase": "bankruptcy",                  "pattern": r"\bbankruptcy\b",                                  "category": "bankruptcy", "weight": 0.6, "lang": "en"},
    {"phrase": "upadłość",                    "pattern": r"\bupadłoś[ćc]\b",                       "category": "bankruptcy", "weight": 0.6, "lang": "pl"},
    {"phrase": "insolvency",                  "pattern": r"\binsolvenc(?:y|ies)\b",                          "category": "bankruptcy", "weight": 0.6, "lang": "en"},
    {"phrase": "niewypłacalność",             "pattern": r"\bniewypełcalnoś[ćc]\b",                "category": "bankruptcy", "weight": 0.6, "lang": "pl"},
    {"phrase": "liquidation",                 "pattern": r"\bliquidation\b",                                 "category": "bankruptcy", "weight": 0.6, "lang": "en"},
    {"phrase": "likwidacja",                  "pattern": r"\blikwidacj[aią]\b",                              "category": "bankruptcy", "weight": 0.6, "lang": "pl"},
    {"phrase": "receivership",                "pattern": r"\breceiversh(?:ip|ips)\b",                        "category": "bankruptcy", "weight": 0.6, "lang": "en"},
    {"phrase": "zarząd komisaryczny",         "pattern": r"\bzarząd\s+komisaryczny\b",                  "category": "bankruptcy", "weight": 0.6, "lang": "pl"},
    {"phrase": "debt restructuring",          "pattern": r"\bdebt\s+restructuring\b",                        "category": "bankruptcy", "weight": 0.6, "lang": "en"},
    {"phrase": "restrukturyzacja długu",      "pattern": r"\brestrukturyzacja\s+długu\b",               "category": "bankruptcy", "weight": 0.6, "lang": "pl"},
    {"phrase": "creditor claims",             "pattern": r"\bcreditor\s+claims\b",                           "category": "bankruptcy", "weight": 0.6, "lang": "en"},
    {"phrase": "wierzytelności",              "pattern": r"\bwierzytelnos[ćc]\b",                            "category": "bankruptcy", "weight": 0.6, "lang": "pl"},
    {"phrase": "niewypełnienie zobowiązań",   "pattern": r"\bniewypełnienie\s+zobowiązań\b",  "category": "bankruptcy", "weight": 0.6, "lang": "pl"},
]
