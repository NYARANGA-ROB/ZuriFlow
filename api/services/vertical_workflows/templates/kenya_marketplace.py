"""Versioned Kenyan industry agent templates for the marketplace wizard."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from api.services.template_marketplace.schema import (
    MarketplaceTemplateListing,
    TemplateVersionInfo,
    TemplateVersionStatus,
)
from api.services.vertical_workflows.schema import (
    BusinessRule,
    IntegrationBindings,
    MultilingualPrompt,
    RuleAction,
    RuleActionType,
    RuleCondition,
    RuleOperator,
    VerticalIndustry,
    VerticalWorkflowTemplate,
    WorkflowStep,
    WorkflowStepKind,
)

TEMPLATE_VERSION = "1.0.0"
TEMPLATE_RELEASED_AT = "2026-08-23"


@dataclass(frozen=True)
class KenyaIndustrySpec:
    industry_id: str
    industry: VerticalIndustry
    name: str
    business_type: str
    description: str
    icon: str
    use_cases: tuple[str, ...]
    faqs: tuple[str, ...]
    collect_fields: tuple[str, ...]
    tools: tuple[str, ...]
    mpesa: bool
    whatsapp: bool
    sms: bool
    greeting_en: str
    greeting_sw: str
    identify_hint: str
    category: str


def _prompt(en: str, sw: str) -> MultilingualPrompt:
    return MultilingualPrompt(
        default_locale="mixed",
        system={"en": en, "sw": sw, "mixed": f"{en} / {sw}"},
    )


def _always_advance(rule_id: str, step_id: str) -> BusinessRule:
    return BusinessRule(
        rule_id=rule_id,
        name=f"Continue to {step_id}",
        when=RuleCondition("field", RuleOperator.ALWAYS),
        then=(RuleAction(RuleActionType.ADVANCE_STEP, {"step_id": step_id}),),
        priority=100,
    )


def _escalate_rule(template_id: str) -> BusinessRule:
    return BusinessRule(
        rule_id=f"{template_id}_escalate",
        name="Escalate to a person",
        when=RuleCondition("intent", RuleOperator.INTENT_IS, "escalation"),
        then=(
            RuleAction(RuleActionType.ESCALATE, {"reason": "caller_requested_human"}),
            RuleAction(RuleActionType.ADVANCE_STEP, {"step_id": "escalation"}),
        ),
        priority=5,
    )


def build_kenya_industry_template(spec: KenyaIndustrySpec) -> VerticalWorkflowTemplate:
    template_id = f"kenya_mp_{spec.industry_id}"
    faqs = "; ".join(spec.faqs)
    fields = ", ".join(spec.collect_fields)
    tools = ", ".join(spec.tools)
    integrations = IntegrationBindings(
        mpesa=spec.mpesa,
        whatsapp=spec.whatsapp,
        sms=spec.sms,
        call_routing=True,
        kenyan_intent=True,
        kenya_hours=True,
        kenya_holidays=True,
        kes=True,
        phone_ke=True,
        crm_timeline=True,
        analytics=True,
        sheng=True,
    )
    metadata: dict[str, Any] = {
        "region": "KE",
        "business_type": spec.business_type,
        "changelog": [
            {
                "version": TEMPLATE_VERSION,
                "released_at": TEMPLATE_RELEASED_AT,
                "notes": "Initial Kenyan industry marketplace release.",
            }
        ],
        "supported_integrations": integrations.to_dict(),
        "default_prompts": {
            "greeting_en": spec.greeting_en,
            "greeting_sw": spec.greeting_sw,
        },
        "default_tools": list(spec.tools),
        "language_configuration": {
            "default": "mixed",
            "supported": ["en", "sw", "sheng", "mixed"],
        },
        "required_env": [
            env
            for env, needed in (
                ("MPESA_CONSUMER_KEY", spec.mpesa),
                ("WHATSAPP_ACCESS_TOKEN", spec.whatsapp),
                ("SMS_PROVIDER_API_KEY", spec.sms),
            )
            if needed
        ],
        "pin_on_install": True,
        "example_use_cases": list(spec.use_cases),
        "icon": spec.icon,
    }
    steps = (
        WorkflowStep(
            step_id="greeting",
            name="Greeting",
            kind=WorkflowStepKind.GREETING,
            next_step_id="language_select",
            prompts=_prompt(spec.greeting_en, spec.greeting_sw),
        ),
        WorkflowStep(
            step_id="language_select",
            name="Language selection",
            kind=WorkflowStepKind.LANGUAGE_SELECT,
            next_step_id="identify",
            prompts=_prompt(
                "Ask whether the caller prefers English, Kiswahili, or a mix including Sheng. Then continue in that language.",
                "Uliza mteja kama anataka Kiingereza, Kiswahili, au mchanganyiko na Sheng. Endelea kwa lugha hiyo.",
            ),
        ),
        WorkflowStep(
            step_id="identify",
            name="Customer identification",
            kind=WorkflowStepKind.IDENTIFY,
            next_step_id="intent",
            prompts=_prompt(
                f"Identify the caller using Kenyan phone numbers when possible. {spec.identify_hint}",
                f"Tambua mteja kwa nambari ya simu ya Kenya inapowezekana. {spec.identify_hint}",
            ),
        ),
        WorkflowStep(
            step_id="intent",
            name="Intent classification",
            kind=WorkflowStepKind.QUALIFY,
            next_step_id="faq",
            rules=(_escalate_rule(template_id),),
            prompts=_prompt(
                f"Classify the reason for the call. Typical needs: {', '.join(spec.use_cases)}.",
                f"Elewa sababu ya simu. Mahitaji ya kawaida: {', '.join(spec.use_cases)}.",
            ),
        ),
        WorkflowStep(
            step_id="faq",
            name="Common FAQs",
            kind=WorkflowStepKind.FAQ,
            next_step_id="collect",
            prompts=_prompt(
                f"Answer common questions: {faqs}. Do not invent policy, prices, or balances.",
                f"Jibu maswali ya kawaida: {faqs}. Usitunge sera, bei, au salio.",
            ),
        ),
        WorkflowStep(
            step_id="collect",
            name="Data collection",
            kind=WorkflowStepKind.COLLECT,
            next_step_id="tools",
            prompts=_prompt(
                f"Collect only what is needed: {fields}. Confirm Kenyan phone numbers and amounts in Kenyan Shillings (KES).",
                f"Kusanya taarifa zinazohitajika: {fields}. Thibitisha nambari za Kenya na kiasi kwa shilingi (KES).",
            ),
        ),
        WorkflowStep(
            step_id="tools",
            name="Business tools",
            kind=WorkflowStepKind.SUPPORT if not spec.mpesa else WorkflowStepKind.COLLECT_PAYMENT,
            next_step_id="escalation",
            rules=(
                *(
                    (
                        BusinessRule(
                            rule_id=f"{template_id}_mpesa",
                            name="Offer M-Pesa",
                            when=RuleCondition("intent", RuleOperator.INTENT_IS, "payment"),
                            then=(RuleAction(RuleActionType.REQUEST_PAYMENT, {"currency": "KES"}),),
                            priority=8,
                        ),
                    )
                    if spec.mpesa
                    else ()
                ),
                *(
                    (
                        BusinessRule(
                            rule_id=f"{template_id}_whatsapp",
                            name="Send WhatsApp follow-up",
                            when=RuleCondition("intent", RuleOperator.INTENT_IS, "follow_up"),
                            then=(
                                RuleAction(
                                    RuleActionType.SEND_WHATSAPP,
                                    {"template": "kenya_follow_up"},
                                ),
                            ),
                            priority=12,
                        ),
                    )
                    if spec.whatsapp
                    else ()
                ),
            ),
            prompts=_prompt(
                f"Use business tools when appropriate: {tools}. Respect Kenyan business hours and public holidays.",
                f"Tumia zana za biashara inapofaa: {tools}. Heshimu saa za kazi na sikukuu za Kenya.",
            ),
        ),
        WorkflowStep(
            step_id="escalation",
            name="Escalation",
            kind=WorkflowStepKind.ESCALATION,
            next_step_id="summary",
            prompts=_prompt(
                "If the caller is upset, asks for a person, or the request is high-risk, transfer to a human with a short briefing.",
                "Ikiwa mteja amekasirika, anaomba mtu, au ombi ni hatari, mpeleke kwa mhudumu na muhtasari mfupi.",
            ),
        ),
        WorkflowStep(
            step_id="summary",
            name="Call summary",
            kind=WorkflowStepKind.SUMMARY,
            next_step_id="closing",
            prompts=_prompt(
                "Summarise what was discussed, next steps, and any follow-up by SMS or WhatsApp. This summary is stored on the CRM timeline for analytics.",
                "Fupisha mazungumzo, hatua zinazofuata, na ufuatiliaji kwa SMS au WhatsApp. Muhtasari huu utahifadhiwa kwenye CRM kwa analytics.",
            ),
        ),
        WorkflowStep(
            step_id="closing",
            name="Closing",
            kind=WorkflowStepKind.CLOSING,
            rules=(
                BusinessRule(
                    rule_id=f"{template_id}_end",
                    name="End call",
                    when=RuleCondition("field", RuleOperator.ALWAYS),
                    then=(RuleAction(RuleActionType.END_WORKFLOW, {}),),
                    priority=1,
                ),
            ),
            prompts=_prompt(
                "Thank the caller in their language and end politely.",
                "Asante mteja kwa lugha yake na umalizie kwa heshima.",
            ),
        ),
    )
    return VerticalWorkflowTemplate(
        template_id=template_id,
        name=spec.name,
        industry=spec.industry,
        version=TEMPLATE_VERSION,
        description=spec.description,
        default_locale="mixed",
        supported_locales=("en", "sw", "sheng", "mixed"),
        entry_step_id="greeting",
        steps=steps,
        global_rules=(_always_advance(f"{template_id}_hours", "greeting"),),
        integrations=integrations,
        metadata=metadata,
    )


KENYA_INDUSTRY_SPECS: tuple[KenyaIndustrySpec, ...] = (
    KenyaIndustrySpec(
        "sacco", VerticalIndustry.SACCO, "SACCOs", "Savings and credit cooperative",
        "Member services for shares, loans, dividends, and M-Pesa deposits.",
        "landmark",
        ("Share balance", "Loan status", "M-Pesa deposit", "Dividend enquiry"),
        ("What is my share balance?", "When is the AGM?", "How do I apply for a loan?"),
        ("member number", "national ID", "phone"),
        ("member lookup", "loan status", "M-Pesa STK", "SMS receipt"),
        True, True, True,
        "Hello, you have reached the SACCO member line. I can help with shares, loans, and deposits.",
        "Habari, umefika kituo cha wanachama wa SACCO. Naweza kusaidia kuhusu shares, mikopo, na amana.",
        "Ask for member number or Kenyan ID.",
        "finance",
    ),
    KenyaIndustrySpec(
        "microfinance", VerticalIndustry.MICROFINANCE, "Microfinance", "Microfinance institution",
        "Loan enquiries, repayment reminders, and group lending support.",
        "wallet",
        ("Loan balance", "Repayment date", "New application", "Group meeting"),
        ("How much do I owe?", "Can I reschedule?", "Where is the field officer?"),
        ("customer name", "loan account", "phone"),
        ("loan lookup", "M-Pesa repayment", "SMS reminder"),
        True, True, True,
        "Hello, this is your microfinance support line. I can help with loans and repayments.",
        "Habari, hii ni laini ya mikopo midogo. Naweza kusaidia kuhusu mikopo na malipo.",
        "Ask for loan account or national ID.",
        "finance",
    ),
    KenyaIndustrySpec(
        "banking", VerticalIndustry.BANKING, "Banks and financial institutions", "Bank or financial institution",
        "Account help, cards, branches, and secure payment guidance.",
        "building",
        ("Account balance", "Card block", "Branch locator", "Fraud alert"),
        ("What are your branch hours?", "How do I reset my PIN?", "Is this transaction genuine?"),
        ("account last 4", "phone", "national ID"),
        ("secure lookup", "M-Pesa paybill help", "escalation to fraud desk"),
        True, True, True,
        "Hello, you have reached the bank helpline. I can help with accounts, cards, and branches.",
        "Habari, umefika kituo cha benki. Naweza kusaidia kuhusu akaunti, kadi, na matawi.",
        "Never ask for a full PIN. Confirm identity with limited details.",
        "finance",
    ),
    KenyaIndustrySpec(
        "insurance", VerticalIndustry.INSURANCE, "Insurance", "Insurer or broker",
        "Policy questions, claims intake, and premium reminders.",
        "shield",
        ("Policy status", "Start a claim", "Premium due", "Cover questions"),
        ("Is my cover active?", "How do I file a claim?", "When is premium due?"),
        ("policy number", "claim description", "phone"),
        ("policy lookup", "claim ticket", "M-Pesa premium"),
        True, True, True,
        "Hello, this is the insurance help line. I can check cover, premiums, and start a claim.",
        "Habari, hii ni laini ya bima. Naweza kuangalia cover, malipo, na kuanza claim.",
        "Ask for policy number and phone.",
        "finance",
    ),
    KenyaIndustrySpec(
        "hospitals", VerticalIndustry.HOSPITALS, "Hospitals and clinics", "Hospital or clinic",
        "Appointments, departments, visiting hours, and patient intake.",
        "heart-pulse",
        ("Book appointment", "Lab results enquiry", "Visiting hours", "Emergency routing"),
        ("Which doctor is on duty?", "Do you take NHIF?", "Where is the pharmacy?"),
        ("patient name", "phone", "preferred date"),
        ("appointment book", "department routing", "WhatsApp confirmation"),
        False, True, True,
        "Hello, you have reached the hospital. I can help with appointments and directions.",
        "Habari, umefika hospitali. Naweza kusaidia kuhusu appointment na maelekezo.",
        "Ask for patient name and phone. Do not give clinical advice.",
        "health",
    ),
    KenyaIndustrySpec(
        "pharmacies", VerticalIndustry.PHARMACIES, "Pharmacies", "Pharmacy or chemist",
        "Stock checks, opening hours, and prescription pickup.",
        "pill",
        ("Medicine availability", "Opening hours", "Prescription pickup", "Delivery"),
        ("Do you have this medicine?", "Can I order for delivery?", "What time do you close?"),
        ("medicine name", "pickup branch", "phone"),
        ("stock check", "M-Pesa till", "SMS when ready"),
        True, True, True,
        "Hello, this is the pharmacy. I can check stock, hours, and pickup.",
        "Habari, hii ni duka la dawa. Naweza kuangalia dawa, saa, na kukusanya.",
        "Ask for the medicine name. Do not prescribe.",
        "health",
    ),
    KenyaIndustrySpec(
        "schools", VerticalIndustry.SCHOOLS, "Schools", "Primary or secondary school",
        "Fees, term dates, transport, and parent enquiries.",
        "school",
        ("Fee balance", "Term dates", "Transport", "Admission"),
        ("How much is outstanding?", "When does term start?", "Is the bus running?"),
        ("student name", "admission number", "parent phone"),
        ("fee lookup", "M-Pesa paybill", "WhatsApp to parent"),
        True, True, True,
        "Hello, you have reached the school office. I can help with fees, dates, and transport.",
        "Habari, umefika ofisi ya shule. Naweza kusaidia kuhusu ada, tarehe, na usafiri.",
        "Ask for student name or admission number.",
        "education",
    ),
    KenyaIndustrySpec(
        "universities", VerticalIndustry.UNIVERSITIES, "Universities", "University or college",
        "Admissions, fees, exams, and campus services.",
        "graduation-cap",
        ("Admission status", "Fee statement", "Exam timetable", "Campus help"),
        ("When is reporting day?", "How do I get a fee structure?", "Where is the registry?"),
        ("student number", "programme", "phone"),
        ("student lookup", "M-Pesa fees", "SMS exam alert"),
        True, True, True,
        "Hello, this is the university help desk. I can help with admissions, fees, and campus information.",
        "Habari, hii ni dawati la chuo. Naweza kusaidia kuhusu admission, ada, na kampasi.",
        "Ask for student number or application ID.",
        "education",
    ),
    KenyaIndustrySpec(
        "real_estate", VerticalIndustry.REAL_ESTATE, "Real-estate agencies", "Estate agency",
        "Property viewing, listings, and buyer or tenant qualification.",
        "home",
        ("Available houses", "Book viewing", "Rent range", "Location"),
        ("Do you have 2-bedroom in Westlands?", "What is the deposit?", "Can I view tomorrow?"),
        ("budget", "preferred county", "phone"),
        ("listing search", "viewing calendar", "WhatsApp brochure"),
        True, True, True,
        "Hello, you have reached the estate agency. I can help with listings and viewings.",
        "Habari, umefika ofisi ya nyumba. Naweza kusaidia kuhusu nyumba na kuona.",
        "Ask for budget in KES and preferred location or county.",
        "property",
    ),
    KenyaIndustrySpec(
        "property_management", VerticalIndustry.PROPERTY_MANAGEMENT, "Property managers", "Property management",
        "Rent collection, repairs, and tenant notices.",
        "building-2",
        ("Rent balance", "Report repair", "Move-in", "Notice"),
        ("Has rent reflected?", "The water is off", "When is inspection?"),
        ("unit number", "tenant name", "phone"),
        ("rent lookup", "M-Pesa rent", "maintenance ticket"),
        True, True, True,
        "Hello, this is property management. I can help with rent, repairs, and notices.",
        "Habari, hii ni usimamizi wa nyumba. Naweza kusaidia kuhusu kodi, matengenezo, na notisi.",
        "Ask for unit or house number.",
        "property",
    ),
    KenyaIndustrySpec(
        "hotels", VerticalIndustry.HOTELS, "Hotels", "Hotel or lodge",
        "Reservations, check-in help, and guest services.",
        "bed",
        ("Room availability", "Booking", "Check-in time", "Amenities"),
        ("Do you have a room tonight?", "Is breakfast included?", "Where is the hotel?"),
        ("dates", "guest name", "phone"),
        ("reservation", "M-Pesa deposit", "WhatsApp confirmation"),
        True, True, True,
        "Hello, you have reached the hotel. I can help with rooms and guest services.",
        "Habari, umefika hoteli. Naweza kusaidia kuhusu vyumba na huduma za wageni.",
        "Ask for dates and number of guests.",
        "hospitality",
    ),
    KenyaIndustrySpec(
        "restaurants", VerticalIndustry.RESTAURANTS, "Restaurants", "Restaurant or cafe",
        "Reservations, menu questions, and delivery or pickup.",
        "utensils",
        ("Table booking", "Menu", "Opening hours", "Delivery"),
        ("Do you have nyama choma tonight?", "Can I book for 8 people?", "Do you deliver to Kilimani?"),
        ("party size", "time", "phone"),
        ("reservation book", "M-Pesa till", "WhatsApp menu"),
        True, True, True,
        "Hello, this is the restaurant. I can help with tables, the menu, and orders.",
        "Habari, hii ni mgahawa. Naweza kusaidia kuhusu meza, menyu, na oda.",
        "Ask for party size and preferred time.",
        "hospitality",
    ),
    KenyaIndustrySpec(
        "ecommerce", VerticalIndustry.ECOMMERCE, "E-commerce", "Online shop",
        "Order tracking, returns, and delivery updates.",
        "store",
        ("Order status", "Returns", "Delivery slot", "Payment"),
        ("Where is my parcel?", "How do I return an item?", "Can I pay on delivery?"),
        ("order number", "phone", "delivery county"),
        ("order lookup", "M-Pesa checkout", "SMS tracking"),
        True, True, True,
        "Hello, you have reached the shop. I can help with orders, delivery, and returns.",
        "Habari, umefika duka. Naweza kusaidia kuhusu oda, delivery, na kurudisha bidhaa.",
        "Ask for order number or phone used at checkout.",
        "retail",
    ),
    KenyaIndustrySpec(
        "logistics", VerticalIndustry.LOGISTICS, "Logistics", "Freight or logistics company",
        "Shipment tracking, pickup scheduling, and quotes.",
        "truck",
        ("Track shipment", "Book pickup", "Delivery ETA", "Quote"),
        ("Where is my cargo?", "Can you collect today?", "What is the Nairobi to Mombasa rate?"),
        ("waybill", "origin", "destination county"),
        ("track shipment", "dispatch", "SMS ETA"),
        True, True, True,
        "Hello, this is logistics. I can help with tracking, pickups, and delivery times.",
        "Habari, hii ni usafirishaji. Naweza kusaidia kuhusu tracking, kukusanya, na delivery.",
        "Ask for waybill or consignee phone.",
        "transport",
    ),
    KenyaIndustrySpec(
        "courier", VerticalIndustry.COURIER, "Courier companies", "Courier or parcel service",
        "Parcel tracking, pickup, and failed-delivery retries.",
        "package",
        ("Track parcel", "Schedule pickup", "Failed delivery", "COD"),
        ("Has my parcel arrived?", "The rider missed me", "How much is Nairobi CBD?"),
        ("tracking number", "phone", "estate"),
        ("parcel track", "M-Pesa COD", "WhatsApp rider update"),
        True, True, True,
        "Hello, you have reached the courier. I can help with parcels and pickups.",
        "Habari, umefika courier. Naweza kusaidia kuhusu parcels na kukusanya.",
        "Ask for tracking number.",
        "transport",
    ),
    KenyaIndustrySpec(
        "matatu", VerticalIndustry.MATATU, "Matatu and shuttle operators", "PSV or shuttle operator",
        "Routes, departure times, and booking for shuttles.",
        "bus",
        ("Next departure", "Fare", "Route", "Booking"),
        ("What time is the next shuttle to Kisumu?", "How much is the fare?", "Do you go via Nakuru?"),
        ("route", "travel date", "phone"),
        ("timetable", "M-Pesa seat", "SMS ticket"),
        True, True, True,
        "Hello, this is the shuttle line. I can help with routes, fares, and bookings.",
        "Habari, hii ni laini ya shuttle. Naweza kusaidia kuhusu njia, nauli, na booking.",
        "Ask for origin, destination, and travel day.",
        "transport",
    ),
    KenyaIndustrySpec(
        "car_dealerships", VerticalIndustry.CAR_DEALERSHIPS, "Car dealerships", "Vehicle dealer",
        "Stock, test drives, and financing enquiries.",
        "car",
        ("Available cars", "Test drive", "Price", "Hire purchase"),
        ("Do you have a Toyota Axio?", "Can I view this weekend?", "Do you accept trade-in?"),
        ("model", "budget KES", "phone"),
        ("inventory", "test-drive diary", "WhatsApp spec sheet"),
        True, True, True,
        "Hello, you have reached the dealership. I can help with cars, prices, and test drives.",
        "Habari, umefika showroom. Naweza kusaidia kuhusu magari, bei, na kuendesha majaribio.",
        "Ask for preferred model and budget in KES.",
        "auto",
    ),
    KenyaIndustrySpec(
        "garages", VerticalIndustry.GARAGES, "Garages", "Garage or service centre",
        "Service booking, repair status, and parts.",
        "wrench",
        ("Book service", "Repair status", "Quote", "Towing"),
        ("Can I bring the car tomorrow?", "Is my car ready?", "Do you service this make?"),
        ("vehicle reg", "issue", "phone"),
        ("job card", "M-Pesa deposit", "SMS when ready"),
        True, True, True,
        "Hello, this is the garage. I can help with servicing, repairs, and collection.",
        "Habari, hii ni garage. Naweza kusaidia kuhusu service, matengenezo, na kukusanya gari.",
        "Ask for number plate and the issue.",
        "auto",
    ),
    KenyaIndustrySpec(
        "travel", VerticalIndustry.TRAVEL, "Travel agencies", "Travel agency",
        "Flights, packages, visas, and itinerary changes.",
        "plane",
        ("Flight quote", "Package", "Visa help", "Change booking"),
        ("What is Nairobi to Dubai in April?", "Do you arrange visas?", "Can I change dates?"),
        ("travel dates", "destination", "phone"),
        ("quote", "M-Pesa deposit", "WhatsApp itinerary"),
        True, True, True,
        "Hello, you have reached the travel agency. I can help with trips, flights, and documents.",
        "Habari, umefika ofisi ya safari. Naweza kusaidia kuhusu ndege, packages, na visa.",
        "Ask for destination and travel dates.",
        "travel",
    ),
    KenyaIndustrySpec(
        "agriculture", VerticalIndustry.AGRICULTURE, "Agricultural businesses", "Agribusiness",
        "Produce orders, farm inputs, and collection points.",
        "sprout",
        ("Input prices", "Produce collection", "Extension advice", "Payment"),
        ("Do you have DAP?", "When is collection at the market?", "How do farmers get paid?"),
        ("farmer name", "location/county", "phone"),
        ("order inputs", "M-Pesa pay", "SMS market day"),
        True, True, True,
        "Hello, this is the agribusiness line. I can help with inputs, produce, and collection.",
        "Habari, hii ni laini ya kilimo. Naweza kusaidia kuhusu pembejeo, mazao, na kukusanya.",
        "Ask for county or market and phone.",
        "agriculture",
    ),
    KenyaIndustrySpec(
        "ngo", VerticalIndustry.NGO, "NGOs", "NGO or community organisation",
        "Programme information, beneficiary help, and field reports.",
        "heart-handshake",
        ("Programme info", "Beneficiary support", "Donation", "Field office"),
        ("How do I register?", "Where is the nearest office?", "How can I donate?"),
        ("caller name", "county", "phone"),
        ("programme FAQ", "case ticket", "WhatsApp field office"),
        True, True, True,
        "Hello, you have reached the organisation. I can share programme information and connect you to the right team.",
        "Habari, umefika shirika. Naweza kutoa habari za program na kukuunganisha na timu sahihi.",
        "Ask for county and how they would like to be helped.",
        "public",
    ),
    KenyaIndustrySpec(
        "government", VerticalIndustry.GOVERNMENT, "Government service desks", "Public service desk",
        "Service information, appointments, and document status — not legal advice.",
        "landmark",
        ("Service hours", "Document status", "Appointment", "Office location"),
        ("What documents do I need?", "Is the office open on the holiday?", "How do I book?"),
        ("service type", "reference number", "phone"),
        ("queue info", "SMS appointment", "handoff to officer"),
        False, True, True,
        "Hello, this is the government service desk. I can share official process information and book a callback.",
        "Habari, hii ni dawati la huduma za serikali. Naweza kutoa taratibu rasmi na kupanga callback.",
        "Ask which service they need. Do not invent legal outcomes.",
        "public",
    ),
    KenyaIndustrySpec(
        "utilities", VerticalIndustry.UTILITIES, "Utilities", "Water, power, or similar utility",
        "Outages, billing, meter issues, and M-Pesa pay.",
        "zap",
        ("Outage", "Bill balance", "Meter", "New connection"),
        ("Why is there no power/water?", "What is my bill?", "How do I pay via M-Pesa?"),
        ("account or meter number", "location", "phone"),
        ("outage status", "M-Pesa bill", "SMS token"),
        True, True, True,
        "Hello, you have reached the utility. I can help with bills, outages, and meters.",
        "Habari, umefika kampuni ya huduma. Naweza kusaidia kuhusu bili, outage, na mita.",
        "Ask for account or meter number and location.",
        "utilities",
    ),
    KenyaIndustrySpec(
        "security", VerticalIndustry.SECURITY, "Security companies", "Guarding or alarm company",
        "Alarm response, guard requests, and site information.",
        "shield",
        ("Alarm follow-up", "Guard request", "Patrol", "Billing"),
        ("Can you send a response team?", "I need extra guards", "Is my site covered?"),
        ("site name", "location", "phone"),
        ("dispatch", "incident ticket", "WhatsApp to control room"),
        True, True, True,
        "Hello, this is the security control room. I can help with alarms, guards, and site cover.",
        "Habari, hii ni control room ya usalama. Naweza kusaidia kuhusu alarm, askari, na site.",
        "For emergencies, collect location first and escalate immediately.",
        "security",
    ),
    KenyaIndustrySpec(
        "contact_center", VerticalIndustry.CONTACT_CENTER, "Customer-support centres", "Contact centre",
        "General support, ticket logging, and callbacks for any Kenyan brand.",
        "headset",
        ("Log ticket", "Check ticket", "Callback", "FAQ"),
        ("I need to speak to someone", "What is the status of my issue?", "Can you call me back?"),
        ("customer name", "phone", "issue summary"),
        ("ticket", "CRM timeline", "SMS/WhatsApp update"),
        True, True, True,
        "Hello, you have reached customer support. I can help with your question or connect you to a person.",
        "Habari, umefika customer care. Naweza kusaidia au kukuunganisha na mhudumu.",
        "Ask for the phone number and a short description of the issue.",
        "support",
    ),
)


KENYA_MARKETPLACE_TEMPLATES: tuple[VerticalWorkflowTemplate, ...] = tuple(
    build_kenya_industry_template(spec) for spec in KENYA_INDUSTRY_SPECS
)


def kenya_marketplace_listings() -> tuple[MarketplaceTemplateListing, ...]:
    listings: list[MarketplaceTemplateListing] = []
    for spec, template in zip(KENYA_INDUSTRY_SPECS, KENYA_MARKETPLACE_TEMPLATES, strict=True):
        listings.append(
            MarketplaceTemplateListing(
                template_id=template.template_id,
                template=template,
                tags=("kenya", spec.category, spec.industry_id),
                search_keywords=(spec.name, spec.business_type, spec.industry_id),
                category=spec.category,
                featured=spec.industry_id in {"sacco", "hospitals", "ecommerce", "contact_center"},
                icon=spec.icon,
                version_history=(
                    TemplateVersionInfo(
                        version=TEMPLATE_VERSION,
                        released_at=TEMPLATE_RELEASED_AT,
                        changelog="Initial Kenyan industry marketplace release.",
                        status=TemplateVersionStatus.PUBLISHED,
                    ),
                ),
            )
        )
    return tuple(listings)
