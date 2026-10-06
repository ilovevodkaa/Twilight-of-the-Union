"""Writes the minimal stub files for every replace_path'd vanilla content folder (see docs/VANILLA_PURGE.md).

Idempotent. Usage: python tools/purge_vanilla.py
Real replacement content (laws, names) is generated here; everything else is a comment-only stub so the
folder exists in the mod and the vanilla files of that folder are not loaded.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# folder -> why it is purged (comment-only stub). Folders with real content are handled below.
STUB_ONLY = [
    "common/national_focus", "common/decisions", "common/decisions/categories", "common/scripted_effects",
    "common/scripted_triggers", "common/on_actions", "common/ai_strategy", "common/ai_strategy_plans",
    "common/ai_areas", "common/ai_focuses", "common/dynamic_modifiers", "common/scripted_localisation",
    "common/scripted_guis", "common/military_industrial_organization/organizations", "common/special_projects",
    "common/aces", "common/raids", "common/bop", "common/units/names", "common/units/names_divisions",
    "common/units/names_ships", "common/units/names_railway_guns", "events", "history/general",
]

STUB = "# Twilight of the Union: vanilla content of this folder (1936 tags, states, characters) is removed with\n" \
       "# replace_path in descriptor.mod. Intentionally empty. See docs/VANILLA_PURGE.md.\n"

LAWS = """\
# Twilight of the Union: the three law categories, replacing vanilla common/ideas/_economic.txt, _trade.txt and
# _manpower.txt (vanilla common/ideas is purged because it is full of 1936 national spirits and advisors).
# Idea names are the vanilla ones so that script (add_ideas, AI, interface) keeps working. Modifier values are
# approximations of the vanilla values and are meant to be re-tuned for the 1990 setting.

ideas = {

	economy = {
		civilian_economy = {
			allowed = { always = no }
			allowed_to_remove = { always = yes }
			default = yes
			cost = 150
			removal_cost = -1
			level = 1
			modifier = {
				consumer_goods_factor = 0.35
			}
		}
		low_economic_mobilisation = {
			allowed = { always = no }
			allowed_to_remove = { always = yes }
			cost = 150
			removal_cost = -1
			level = 2
			modifier = {
				consumer_goods_factor = 0.30
				production_factory_max_efficiency_factor = 0.05
				industrial_capacity_factory = 0.05
			}
		}
		partial_economic_mobilisation = {
			allowed = { always = no }
			allowed_to_remove = { always = yes }
			cost = 150
			removal_cost = -1
			level = 3
			modifier = {
				consumer_goods_factor = 0.25
				production_factory_max_efficiency_factor = 0.10
				industrial_capacity_factory = 0.10
				production_speed_buildings_factor = 0.10
			}
		}
		war_economy = {
			allowed = { always = no }
			allowed_to_remove = { always = yes }
			cost = 150
			removal_cost = -1
			level = 4
			modifier = {
				consumer_goods_factor = 0.20
				production_factory_max_efficiency_factor = 0.15
				industrial_capacity_factory = 0.15
				production_speed_buildings_factor = 0.15
				stability_factor = -0.05
			}
		}
		tot_economic_mobilisation = {
			allowed = { always = no }
			allowed_to_remove = { always = yes }
			cost = 150
			removal_cost = -1
			level = 5
			modifier = {
				consumer_goods_factor = 0.10
				production_factory_max_efficiency_factor = 0.20
				industrial_capacity_factory = 0.20
				production_speed_buildings_factor = 0.20
				stability_factor = -0.10
			}
		}
	}

	trade_laws = {
		free_trade = {
			allowed = { always = no }
			allowed_to_remove = { always = yes }
			default = yes
			cost = 150
			removal_cost = -1
			level = 1
			modifier = {
				trade_opinion_factor = 0.15
				min_export = 0.1
			}
		}
		export_focus = {
			allowed = { always = no }
			allowed_to_remove = { always = yes }
			cost = 150
			removal_cost = -1
			level = 2
			modifier = {
				trade_opinion_factor = 0.10
				min_export = 0.25
			}
		}
		limited_exports = {
			allowed = { always = no }
			allowed_to_remove = { always = yes }
			cost = 150
			removal_cost = -1
			level = 3
			modifier = {
				trade_opinion_factor = 0.05
				min_export = 0.5
			}
		}
		closed_economy = {
			allowed = { always = no }
			allowed_to_remove = { always = yes }
			cost = 150
			removal_cost = -1
			level = 4
			modifier = {
				trade_opinion_factor = -0.10
				min_export = 0.9
			}
		}
	}

	mobilization_laws = {
		volunteer_only = {
			allowed = { always = no }
			allowed_to_remove = { always = yes }
			default = yes
			cost = 150
			removal_cost = -1
			level = 1
			modifier = {
				conscription_factor = 0.02
			}
		}
		limited_conscription = {
			allowed = { always = no }
			allowed_to_remove = { always = yes }
			cost = 150
			removal_cost = -1
			level = 2
			modifier = {
				conscription_factor = 0.05
			}
		}
		extensive_conscription = {
			allowed = { always = no }
			allowed_to_remove = { always = yes }
			cost = 150
			removal_cost = -1
			level = 3
			modifier = {
				conscription_factor = 0.10
			}
		}
		service_by_requirement = {
			allowed = { always = no }
			allowed_to_remove = { always = yes }
			cost = 150
			removal_cost = -1
			level = 4
			modifier = {
				conscription_factor = 0.15
				stability_factor = -0.05
			}
		}
		all_adults_serve = {
			allowed = { always = no }
			allowed_to_remove = { always = yes }
			cost = 150
			removal_cost = -1
			level = 5
			modifier = {
				conscription_factor = 0.20
				stability_factor = -0.10
			}
		}
		scraping_the_barrel = {
			allowed = { always = no }
			allowed_to_remove = { always = yes }
			cost = 150
			removal_cost = -1
			level = 6
			modifier = {
				conscription_factor = 0.30
				stability_factor = -0.15
			}
		}
		disarmed_nation = {
			allowed = { always = no }
			allowed_to_remove = { always = yes }
			cost = 150
			removal_cost = -1
			level = 0
			modifier = {
				conscription_factor = -0.05
			}
		}
	}
}
"""

TRAITS = """\
# Twilight of the Union: minimal country leader trait file (vanilla common/country_leader is purged).
# Traits for the 1990 leaders are added here later.
leader_traits = {
	TOTU_leader_placeholder = {
	}
}
"""

# ---- name pools (placeholder generic lists, tag -> pool)
POOLS = {
    "slavic": (["Ivan", "Pyotr", "Andrei", "Mikhail", "Sergei", "Nikolai", "Vladimir", "Jan", "Josef", "Tomasz", "Marko", "Dmitri"],
               ["Anna", "Maria", "Olga", "Elena", "Irina", "Natalia", "Katarina", "Ludmila"],
               ["Ivanov", "Petrov", "Smirnov", "Kowalski", "Novak", "Horvat", "Popov", "Kuznetsov", "Nowak", "Dvorak", "Markovic", "Volkov"]),
    "germanic": (["Hans", "Karl", "Peter", "Wilhelm", "Jan", "Lars", "Erik", "Johann", "Klaus", "Thomas", "Pieter", "Anders"],
                 ["Anna", "Greta", "Ingrid", "Maria", "Karin", "Eva", "Sofie", "Helga"],
                 ["Mueller", "Schmidt", "Weber", "Jansen", "de Vries", "Andersson", "Hansen", "Larsen", "Berg", "Vogel", "Bauer", "Koch"]),
    "romance": (["Jean", "Pierre", "Giovanni", "Marco", "Jose", "Antonio", "Luis", "Carlos", "Mario", "Andre", "Paolo", "Manuel"],
                ["Maria", "Marie", "Giulia", "Isabel", "Carmen", "Sofia", "Lucia", "Ana"],
                ["Martin", "Dubois", "Rossi", "Ferrari", "Garcia", "Silva", "Lopez", "Costa", "Moreau", "Bianchi", "Santos", "Fernandez"]),
    "anglo": (["John", "James", "William", "Robert", "George", "David", "Michael", "Thomas", "Peter", "Richard", "Henry", "Paul"],
              ["Mary", "Elizabeth", "Margaret", "Susan", "Jane", "Helen", "Sarah", "Anne"],
              ["Smith", "Jones", "Brown", "Taylor", "Wilson", "Davies", "Clark", "Walker", "Hall", "Wright", "Young", "King"]),
    "eastasian": (["Wei", "Jun", "Hiroshi", "Takeshi", "Min", "Jian", "Kenji", "Hyun", "Yong", "Tran", "Somchai", "Budi"],
                  ["Mei", "Yuki", "Hana", "Lin", "Sakura", "Mina", "Lan", "Siti"],
                  ["Wang", "Li", "Zhang", "Tanaka", "Suzuki", "Kim", "Park", "Nguyen", "Chen", "Sato", "Lee", "Santoso"]),
    "arabic": (["Mohammed", "Ahmed", "Ali", "Hassan", "Omar", "Khalid", "Yusuf", "Ibrahim", "Mustafa", "Abdullah", "Karim", "Saleh"],
               ["Fatima", "Aisha", "Layla", "Mariam", "Noor", "Zainab", "Amira", "Salma"],
               ["Al-Said", "Hashemi", "Mansour", "Haddad", "Nasser", "Farouk", "Rahman", "Qasim", "Khalil", "Aziz", "Bakr", "Sayed"]),
    "indic": (["Rajiv", "Amit", "Vijay", "Arjun", "Sanjay", "Anil", "Ravi", "Imran", "Rahim", "Nimal", "Hasan", "Kamal"],
              ["Priya", "Sunita", "Anita", "Lakshmi", "Meera", "Fatima", "Nirmala", "Sita"],
              ["Singh", "Sharma", "Patel", "Khan", "Gupta", "Kumar", "Rao", "Das", "Ahmed", "Silva", "Perera", "Hossain"]),
    "african": (["Kwame", "Joseph", "Emmanuel", "Samuel", "Moses", "Daniel", "Patrick", "Thomas", "Abebe", "Jomo", "Peter", "Ibrahim"],
                ["Amina", "Grace", "Esther", "Mercy", "Fatou", "Akosua", "Ruth", "Sarah"],
                ["Mensah", "Okafor", "Diallo", "Traore", "Kamau", "Mwangi", "Banda", "Nkosi", "Tesfaye", "Sow", "Ndlovu", "Osei"]),
    "latin": (["Jose", "Juan", "Carlos", "Luis", "Miguel", "Pedro", "Jorge", "Ricardo", "Fernando", "Alberto", "Roberto", "Diego"],
              ["Maria", "Ana", "Carmen", "Rosa", "Lucia", "Sofia", "Isabel", "Elena"],
              ["Gonzalez", "Rodriguez", "Perez", "Sanchez", "Ramirez", "Torres", "Flores", "Rivera", "Gomez", "Diaz", "Cruz", "Morales"]),
}
TAG_POOL = {}
for pool, tags in {
    "slavic": "SOV POL CZE BUL YUG ROM",
    "germanic": "GER DDR AUS HOL BEL SWI DEN NOR SWE ICE LUX LIE FIN",
    "romance": "FRA ITA SPR POR AND MCO SMR MLT GRE ALB",
    "anglo": "USA ENG CAN AST NZL IRE JAM BHS TTO BRB BLZ GUY ATG DMA GRD KNA LCA VCT FIJ SLB TON TUV KIR NRU WSM PNG FSM MHL PLW SYC MUS",
    "eastasian": "JAP PRC CHI KOR PRK MON VIN LAO CAM SIA BRM MAL NEI PHI SIN BRU",
    "arabic": "EGY LBA TUN ALG MOR MRT SUD SAU YEM YES OMA UAE QAT KUW BHR IRQ SYR LEB TRJ ISR PER TUR AFG SOM DJI COM",
    "indic": "RAJ PAK BAN CEY NEP BHU MDV",
    "latin": "MEX BRA ARG CHL PRU COL VEN BOL URG PAR ECU CUB DOM HAI COS GUA HON NIC PAN SAL SUR CPV",
}.items():
    for t in tags.split():
        TAG_POOL[t] = pool


def names_file(tags):
    out = ["# Twilight of the Union: PLACEHOLDER name lists, one generic pool per language area (vanilla common/names is purged).",
           "# Generated by tools/purge_vanilla.py.", ""]
    for tag in sorted(tags):
        m, f, s = POOLS[TAG_POOL.get(tag, "african")]
        q = lambda l: " ".join(f'"{x}"' for x in l)
        out.append(f"{tag} = {{\n\tmale = {{\n\t\tnames = {{ {q(m)} }}\n\t\tsurnames = {{ {q(s)} }}\n"
                   f"\t\tcallsigns = {{ \"Falcon\" \"Hawk\" \"Viper\" \"Eagle\" \"Wolf\" \"Raven\" }}\n\t}}\n"
                   f"\tfemale = {{\n\t\tnames = {{ {q(f)} }}\n\t\tsurnames = {{ {q(s)} }}\n\t}}\n}}\n")
    return "\n".join(out)


def tags_in_mod():
    import re
    txt = (ROOT / "common/country_tags/totu_countries.txt").read_text(encoding="utf-8")
    return re.findall(r"^([A-Z0-9]{3})\s*=", txt, re.M)


def put(rel, text):
    p = ROOT / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def main():
    for d in STUB_ONLY:
        put(f"{d}/totu_stub.txt", STUB)
    put("common/ideas/totu_laws.txt", LAWS)
    put("common/country_leader/totu_traits.txt", TRAITS)
    put("common/names/totu_names.txt", names_file(tags_in_mod()))
    print("ok")


if __name__ == "__main__":
    main()
