(function(){
  const dict = {
    sv: { nav_why:"Varför Yuplan", nav_modules:"Moduler", nav_how:"Så funkar det", nav_contact:"Kontakt", cta_header:"Boka demo",
      hero_tag:"Från meny till servering – utan friktion", hero_title_1:"Smart matplanering & produktion", hero_title_2:"för alla storkök & köksflöden",
      hero_sub:"Yuplan hjälper kommuner, skolor, vård, catering, företagsrestauranger och storkök att planera, producera och leverera mat – med kontroll på specialkost, resurser och svinn.",
      cta_primary:"Boka en kostnadsfri demo", cta_secondary:"Utforska modulerna", hero_note:"Ingen installation. Fungerar på dator, surfplatta och mobil.",
  avatar_caption:"Scrolla lite… hen visar flödet på surfplattan 👀", kpi_uptime:"drifttid", kpi_waste:"svinn", kpi_speed:"planering", kpi_audit:"spårbarhet", kpi_uptime_desc:"stabil drift", kpi_waste_desc:"kontroll & minskning", kpi_speed_desc:"snabbt & tydligt", kpi_audit_desc:"full historik",
      why_title:"Ett verktyg som jobbar som ni jobbar", why_body:"Yuplan automatiserar repetitiva moment, ger klara listor för dagen, hanterar specialkost utan dubbelarbete och stöttar menyval – allt beskrivs tydligt för personal och avdelningar utan att låsa arbetssättet.",
  why_1:"Snabb menybyggare – återanvänd veckor, komponenter och recept.", why_2:"Planeringsvy – se vem som kan äta vad och vilka som behöver anpassning.", why_3:"Rapporter – tydlig veckostatistik inkl. normalkost & specialkost.", why_4:"Kom ihåg att beställa – smart inköpslista kopplad till meny och recept.", why_5:"Fungerar i stor skala – flera kök, enheter och roller.",
      why_card1_t:"Mindre krångel", why_card1_b:"Mindre admin, färre fel. Få rätt info till rätt roll i rätt tid.", why_card2_t:"Mer kontroll", why_card2_b:"Boende-/gästbehov, specialkost och produktion i synk.",
      why_card3_t:"Mindre svinn", why_card3_b:"Frysplock & preppverktyg som minskar överproduktion.", why_card4_t:"Snabbare start", why_card4_b:"Ingen installation. Kör i browsern på mobil och surfplatta.",
      modules_title:"Bygg ert flöde med moduler", mod_menu_kicker:"Meny", mod_menu_title:"Menybyggare", mod_menu_body:"Dra-och-släpp veckor, återanvänd komponenter och beskriv menyval för avdelningar. Koppla recept när ni vill – inget tvång.",
      mod_menu_1:"Komponentbank & mallar", mod_menu_2:"Synliga menyval per avdelning", mod_menu_3:"Versionshantering & dubblettskydd", mod_plan_kicker:"Planering", mod_plan_title:"Planeringsvy",
      mod_plan_body:"Dagliga listor på vilka som kan äta vad, vilka som behöver anpassning och hur många portioner som krävs.", mod_plan_1:"Avdelnings- & köksperspektiv", mod_plan_2:"Tydliga menyval", mod_plan_3:"Förmarkeringar för kosttyper",
      mod_rec_kicker:"Recept", mod_rec_title:"Recept & skalning", mod_rec_body:"Skapa/importera recept, välj synlighet (privat/site/org), skala efter antal och koppla till menyrader när det passar.", mod_rec_1:"Kategori & delning inom org",
      mod_rec_2:"Snabb skalning & portionsutbyte", mod_rec_3:"Telemetri på användning", mod_rep_kicker:"Rapporter", mod_rep_title:"Rapporter & export",
      mod_rep_body:"Veckosammanställningar per avdelning, måltid och kosttyp. Export till PDF/Excel med tydliga varningar om uppgifter saknas.", mod_rep_1:"Normalkost & specialkost", mod_rep_2:"Filter per vecka och enhet", mod_rep_3:"Mobilvänlig läsbarhet",
  mod_ord_kicker:"Beställning", mod_ord_title:"Kom ihåg att beställa", mod_ord_body:"Påminnelselistor per dag och site utifrån aktuell meny & recept. Mottagare bockar av – listan nollställs enligt schema.", mod_ord_1:"Fasta dagar & mottagare",
      mod_ord_2:"Fria punkter från kockstartsidan", mod_ord_3:"API-klar för leverantörer", mod_prep_kicker:"Produktion", mod_prep_title:"Prepp & frysplock",
      mod_prep_body:"Prepp-checklistor, ansvar/tider och förslag på frysplock baserat på historik och lager – smart svinnreducering.", mod_prep_1:"Mallar per komponent", mod_prep_2:"Telemetri på moment", mod_prep_3:"Offshore-logik vidareutvecklad",
  how_title:"Så funkar det", how_body_1:"Klart uppdelade vyer för planering, produktion och uppföljning. Ni beskriver val och behov i text – systemet summerar och guidar.",
      how_li1:"Bygg eller importera menyveckor. Lägg till komponenter vid behov.", how_li2:"Beskriv valen i text – avdelningar ser exakt vad som gäller.", how_li3:"Förmarkera kosttyper som alltid anpassas.", how_li4:"Klicka i planerings- och personalvy – Yuplan summerar portioner.", how_li5:"Rapportera veckan, exportera PDF/Excel, optimera prepp & frysplock.",
      how_callout_t:"Resultat ni märker direkt", how_c1:"Mindre manuellt dubbelarbete", how_c2:"Färre fel i anpassningar och mängder", how_c3:"Mer tid till matlagning och kvalitet",
      cta_title:"Redo att se Yuplan live?", cta_body:"Vi visar hur ni planerar, producerar och rapporterar utan friktion. Anpassat för er verksamhet – oavsett om det är kommun, skola, vård, catering, storkök eller företagsrestaurang.",
  cta_button:"Boka demo", cta_hint:"Eller mejla oss: info@yuplan.se", form_name:"Namn", form_email:"E-post", form_msg:"Meddelande", form_send:"Skicka", form_thanks:"Tack! Vi hör av oss inom kort.", foot_rights:"Alla rättigheter förbehållna.",
      features_title:"Funktioner – tydligt och enkelt", feat_menu_t:"Meny", feat_menu_b1:"Dra-och-släpp veckor och komponenter", feat_menu_b2:"Synliga menyval per avdelning/enhet",
      feat_plan_t:"Planering", feat_plan_b1:"Vem kan äta vad, vilka behöver anpassning", feat_plan_b2:"Automatiska summeringar av portioner",
      feat_rec_t:"Recept", feat_rec_b1:"Skalning och delning inom organisation", feat_rec_b2:"Koppla vid behov – inget tvång",
      feat_rep_t:"Rapporter", feat_rep_b1:"Normalkost & specialkost per vecka/enhet", feat_rep_b2:"Export till PDF/Excel",
      feat_ord_t:"Beställning", feat_ord_b1:"“Kom ihåg att beställa”-listor per dag/site", feat_ord_b2:"Fasta mottagare och fria punkter",
      feat_prod_t:"Produktion", feat_prod_b1:"Prepp-checklistor och ansvar/tider", feat_prod_b2:"Frysplock-förslag minskar svinn",
      seg_kommun:"Kommun", seg_offshore:"Offshore", seg_banquet:"Bankett/Storkök"
    },
    no: { nav_why:"Hvorfor Yuplan", nav_modules:"Moduler", nav_how:"Slik fungerer det", nav_contact:"Kontakt", cta_header:"Book demo",
      hero_tag:"Fra meny til servering – uten friksjon", hero_title_1:"Smart matplanlegging & produksjon", hero_title_2:"for alle storkjøkken & kjøksflyt",
      hero_sub:"Yuplan hjelper kommuner, skoler, helse, catering, bedriftskantiner og storkjøkken å planlegge, produsere og levere mat – med kontroll på spesialkost, ressurser og svinn.",
      cta_primary:"Book en uforpliktende demo", cta_secondary:"Utforsk modulene", hero_note:"Ingen installasjon. Fungerer på PC, nettbrett og mobil.",
  avatar_caption:"Scroll litt… hen viser flyten på nettbrettet 👀", kpi_uptime:"oppetid", kpi_waste:"svinn", kpi_speed:"planlegging", kpi_audit:"sporbarhet", kpi_uptime_desc:"stabil drift", kpi_waste_desc:"kontroll & reduksjon", kpi_speed_desc:"raskt & tydelig", kpi_audit_desc:"full historikk",
      why_title:"Et verktøy som jobber slik dere jobber", why_body:"Yuplan automatiserer gjentakende oppgaver, gir klare dagslister, håndterer spesialkost uten dobbeltarbeid og støtter menyvalg – tydelig for ansatte og avdelinger.",
      why_1:"Rask menybygger – gjenbruk uker, komponenter og oppskrifter.", why_2:"Planleggingsvisning – se hvem som kan spise hva, og hvem som trenger tilpasning.", why_3:"Rapporter – tydelig ukestatistikk inkl. normalkost & spesialkost.", why_4:"“Husk å bestille” – smart innkjøpsliste koblet til meny og oppskrifter.", why_5:"Skalerer – flere kjøkken, enheter og roller.",
      why_card1_t:"Mindre styr", why_card1_b:"Mindre admin, færre feil. Riktig info til riktig rolle.", why_card2_t:"Mer kontroll", why_card2_b:"Behov, spesialkost og produksjon i synk.", why_card3_t:"Mindre svinn", why_card3_b:"Fryseplukk & prepp som reduserer overproduksjon.", why_card4_t:"Rask oppstart", why_card4_b:"Ingen installasjon. Kjør i nettleseren.",
      modules_title:"Bygg flyten deres med moduler", mod_menu_kicker:"Meny", mod_menu_title:"Menybygger", mod_menu_body:"Dra-og-slipp uker, gjenbruk komponenter og beskriv menyvalg for avdelinger.",
      mod_menu_1:"Komponentbank & maler", mod_menu_2:"Synlige menyvalg per avdeling", mod_menu_3:"Versjonering & duplikatvern", mod_plan_kicker:"Planlegging", mod_plan_title:"Planleggingsvisning",
      mod_plan_body:"Daglige lister over hvem som kan spise hva, hvem som trenger tilpasning, og hvor mange porsjoner som trengs.", mod_plan_1:"Avdelings- & kjøkkenperspektiv", mod_plan_2:"Tydelige menyvalg", mod_plan_3:"Forvalgte kosttyper",
      mod_rec_kicker:"Oppskrifter", mod_rec_title:"Oppskrifter & skalering", mod_rec_body:"Lag/importer oppskrifter, velg synlighet, skaler og koble ved behov.", mod_rec_1:"Kategorier & deling", mod_rec_2:"Rask skalering & porsjonsbytte", mod_rec_3:"Telemetri på bruk",
      mod_rep_kicker:"Rapporter", mod_rep_title:"Rapporter & eksport", mod_rep_body:"Ukessammendrag per avdeling, måltid og kosttype. Eksport til PDF/Excel.", mod_rep_1:"Normalkost & spesialkost", mod_rep_2:"Filter per uke og enhet", mod_rep_3:"Mobilvennlig",
  mod_ord_kicker:"Bestilling", mod_ord_title:"Husk å bestille", mod_ord_body:"Påminnelselister per dag og site.", mod_ord_1:"Faste dager & mottakere", mod_ord_2:"Frie punkter", mod_ord_3:"API-klar",
      mod_prep_kicker:"Produksjon", mod_prep_title:"Prepp & fryseplukk", mod_prep_body:"Prepp-sjekklister, ansvar/tider og forslag basert på historikk og lager.", mod_prep_1:"Maler per komponent", mod_prep_2:"Telemetri på prosesser", mod_prep_3:"Offshore-logikk videreutviklet",
  how_title:"Slik fungerer det", how_body_1:"Tydelige visninger for planlegging, produksjon og oppfølging. Dere beskriver valg og behov – systemet summerer og veileder.",
      how_li1:"Bygg/importer menyuker.", how_li2:"Beskriv valgene i tekst.", how_li3:"Forvalg for kosttyper som alltid tilpasses.", how_li4:"Klikk i visninger – Yuplan summerer.", how_li5:"Rapporter uken, eksporter, optimaliser.",
      how_callout_t:"Resultater dere merker", how_c1:"Mindre dobbeltarbeid", how_c2:"Færre feil", how_c3:"Mer tid til matlaging",
  cta_title:"Klar for å se Yuplan live?", cta_body:"Vi viser hvordan dere planlegger, produserer og rapporterer uten friksjon.", cta_button:"Book demo", cta_hint:"Eller e-post: info@yuplan.se", form_name:"Navn", form_email:"E-post", form_msg:"Melding", form_send:"Send", form_thanks:"Takk! Vi tar kontakt snart.", foot_rights:"Alle rettigheter forbeholdt.",
      features_title:"Funksjoner – tydelig og enkelt", feat_menu_t:"Meny", feat_menu_b1:"Dra-og-slipp uker og komponenter", feat_menu_b2:"Synlige valg per avdeling/enhet",
      feat_plan_t:"Planlegging", feat_plan_b1:"Hvem kan spise hva, hvem trenger tilpasning", feat_plan_b2:"Automatiske summeringer av porsjoner",
      feat_rec_t:"Oppskrifter", feat_rec_b1:"Skalering og deling i organisasjonen", feat_rec_b2:"Koble ved behov – ikke tvang",
      feat_rep_t:"Rapporter", feat_rep_b1:"Standard- og spesialkost per uke/enhet", feat_rep_b2:"Eksport til PDF/Excel",
      feat_ord_t:"Bestilling", feat_ord_b1:"“Husk å bestille”-lister per dag/site", feat_ord_b2:"Faste mottakere og frie punkter",
      feat_prod_t:"Produksjon", feat_prod_b1:"Prepp-sjekklister og ansvar/tider", feat_prod_b2:"Fryseplukk-forslag reduserer svinn",
      seg_kommun:"Kommune", seg_offshore:"Offshore", seg_banquet:"Bankett/Storkjøkken"
    },
  en: { nav_why:"Why Yuplan", nav_modules:"Modules", nav_how:"How it works", nav_contact:"Contact", cta_header:"Book demo",
      hero_tag:"From menu to serving—without friction", hero_title_1:"Smart meal planning & production", hero_title_2:"for every large-scale kitchen flow",
      hero_sub:"Yuplan helps municipalities, schools, healthcare, catering, corporate canteens and large kitchens plan, produce and deliver food—with control over dietary needs, resources and waste.",
      cta_primary:"Book a free demo", cta_secondary:"Explore modules", hero_note:"No install. Works on desktop, tablet and phone.",
  avatar_caption:"Scroll a little… showing flow on the tablet 👀", kpi_uptime:"uptime", kpi_waste:"waste", kpi_speed:"planning", kpi_audit:"traceability", kpi_uptime_desc:"stable ops", kpi_waste_desc:"controlled & reduced", kpi_speed_desc:"fast & clear", kpi_audit_desc:"full history",
      why_title:"A tool that works the way you work", why_body:"Yuplan automates repetitive tasks and supports department menu choices clearly.",
      why_1:"Fast menu builder—re-use weeks, components and recipes.", why_2:"Planning view—who can eat what and who needs adaptations.", why_3:"Reports—clear weekly stats.", why_4:"“Remember to order”—smart purchasing.", why_5:"Scales across multiple kitchens and roles.",
      why_card1_t:"Less hassle", why_card1_b:"Less admin, fewer mistakes.", why_card2_t:"More control", why_card2_b:"Needs, diets and production in sync.", why_card3_t:"Less waste", why_card3_b:"Freezer-pick & prep reduce overproduction.", why_card4_t:"Faster start", why_card4_b:"Runs in your browser.",
      modules_title:"Assemble your flow with modules", mod_menu_kicker:"Menu", mod_menu_title:"Menu Builder", mod_menu_body:"Drag-and-drop menus and describe unit choices in plain text.",
      mod_menu_1:"Component library & templates", mod_menu_2:"Visible choices per unit", mod_menu_3:"Versioning & duplicate guard", mod_plan_kicker:"Planning", mod_plan_title:"Planning View",
      mod_plan_body:"Daily lists of who can eat what and how many portions.", mod_plan_1:"Unit & kitchen perspectives", mod_plan_2:"Clear choices", mod_plan_3:"Preselected diet types",
      mod_rec_kicker:"Recipes", mod_rec_title:"Recipes & Scaling", mod_rec_body:"Create/import recipes with visibility and scaling.", mod_rec_1:"Categories & sharing", mod_rec_2:"Quick scaling & swaps", mod_rec_3:"Usage telemetry",
      mod_rep_kicker:"Reports", mod_rep_title:"Reports & Export", mod_rep_body:"Weekly breakdown and exports.", mod_rep_1:"Standard & special diets", mod_rep_2:"Filters by week & site", mod_rep_3:"Mobile-friendly",
  mod_ord_kicker:"Ordering", mod_ord_title:"Remember to order", mod_ord_body:"Reminder lists by day and site.", mod_ord_1:"Fixed days & recipients", mod_ord_2:"Free items", mod_ord_3:"Vendor-ready APIs",
      mod_prep_kicker:"Production", mod_prep_title:"Prep & Freezer-Pick", mod_prep_body:"Checklists and suggestions based on history & stock.", mod_prep_1:"Templates per component", mod_prep_2:"Step telemetry", mod_prep_3:"Enhanced offshore logic",
  how_title:"How it works", how_body_1:"Clear views for planning, production and follow-up. You describe choices and needs – the system sums and guides.", how_li1:"Build/import menu weeks.", how_li2:"Describe choices in text.", how_li3:"Preselect diet types.", how_li4:"Click in planning/staff views—Yuplan sums.", how_li5:"Report the week and export.",
      how_callout_t:"Results you feel immediately", how_c1:"Less double work", how_c2:"Fewer mistakes", how_c3:"More time for cooking",
  cta_title:"Ready to see Yuplan live?", cta_body:"We’ll show how you plan, produce and report without friction.", cta_button:"Book demo", cta_hint:"Or email us: info@yuplan.se", form_name:"Name", form_email:"Email", form_msg:"Message", form_send:"Send", form_thanks:"Thanks! We’ll get back shortly.", foot_rights:"All rights reserved.",
      features_title:"Features – clear and simple", feat_menu_t:"Menu", feat_menu_b1:"Drag-and-drop weeks and components", feat_menu_b2:"Visible choices per unit",
      feat_plan_t:"Planning", feat_plan_b1:"Who can eat what and who needs adaptations", feat_plan_b2:"Automatic portion summaries",
      feat_rec_t:"Recipes", feat_rec_b1:"Scaling and sharing across the org", feat_rec_b2:"Link when needed – not forced",
      feat_rep_t:"Reports", feat_rep_b1:"Standard & special diets by week/site", feat_rep_b2:"Export to PDF/Excel",
      feat_ord_t:"Ordering", feat_ord_b1:"“Remember to order” lists by day/site", feat_ord_b2:"Fixed recipients and free items",
      feat_prod_t:"Production", feat_prod_b1:"Prep checklists and responsibilities/times", feat_prod_b2:"Freezer-pick suggestions reduce waste",
      seg_kommun:"Municipal", seg_offshore:"Offshore", seg_banquet:"Banquet/Large Kitchen"
    }
  };
  let current = 'sv';
  function t(key){ return (dict[current] && dict[current][key]) || key; }
  function setLang(lang){
    current = dict[lang] ? lang : 'sv';
    document.documentElement.lang = current;
    document.querySelectorAll('[data-i18n]').forEach(n=>{ n.textContent = t(n.getAttribute('data-i18n')); });
    document.querySelectorAll('.lang__btn').forEach(b=> b.classList.toggle('is-active', b.dataset.lang===current));
    try{ localStorage.setItem('yuplan_lang', current); }catch{}
  }
  window.i18n = { setLang, t };
  window.addEventListener('DOMContentLoaded', ()=>{
    const saved = (localStorage.getItem('yuplan_lang')||'sv');
    setLang(saved);
    document.querySelectorAll('.lang__btn').forEach(btn=> btn.addEventListener('click', ()=> setLang(btn.dataset.lang)));
  });
})();
