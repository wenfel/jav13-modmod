# Weapon-origin estimation notes

This file records deliberate gameplay-oriented approximations used by the JA2 v1.13 country-of-origin mod.

The project is not intended to be a museum-grade firearms catalogue. When a JA2 row clearly points at a real manufacturer or weapon family but the exact factory variant, submodel, or serial-production dates are uncertain, the manifest may use `ESTIMATED` instead of leaving the row unusable.

## Rules

- `ESTIMATED` means the row is a best-fit interpretation for gameplay, not a claim of exact historical provenance.
- Estimated rows use `MEDIUM` confidence, require a nonzero origin mask, a provenance entry, and an explanatory manifest note.
- Origin is prioritized over exact production dates.
- Approximate years are used only when there is a reasonable family/model-era anchor. Otherwise the year remains `0`.
- A manufacturer/design family may be used as the best-fit origin for game-specific conversions.
- Historical-state distinctions are still respected where they are obvious (for example Soviet designs remain `SOVIET_UNION`; P-08 uses `GERMANY_PRE_1949`).
- `PROTOTYPE` remains separate for weapons that genuinely never reached normal serial production.
- Truly unidentifiable rows remain `AMBIGUOUS_VARIANT` and zero-valued.

## Estimated rows

| uiIndex | JA2 item | Best-fit origin | Years | Rationale |
| ---: | --- | --- | --- | --- |
| 12 | Commando | USA | 0–0 | Treat JA2 'Colt M4 Commando' as a US Colt Commando/M4-family carbine; exact Colt model number is intentionally not distinguished. |
| 336 | SIG P226R | USA|GERMANY | 0–0 | Rail-era P226 manufacture spans SIG Sauer facilities in Germany and the USA; use both as a pragmatic best-fit. |
| 613 | AKS-47 | SOVIET_UNION | 0–0 | Treat game label AKS-47 as the folding-stock Soviet AK/AKS lineage rather than requiring a formal model-name match. |
| 631 | M1911A1 Hi-Cap | USA | 0–0 | Treat the high-capacity M1911A1 as a US commercial/custom M1911 derivative; exact Colt catalog model is not required for gameplay metadata. |
| 647 | FAL Carbine | BELGIUM | 0–0 | Treat generic FN FAL Carbine as an FN Herstal Belgian short/Para FAL variant; exact 50.xx submodel is not material to the mod. |
| 648 | FAL OSW | USA | 2003–0 | Interpret 'FAL OSW' as the US DSA SA58 OSW family; approximate production start 2003. |
| 657 | Gepard M2 | HUNGARY | 1989–0 | Hungarian Gepard M2 prototype/early model was completed in 1989; use Hungary and 1989 as the earliest best-fit bound. |
| 668 | MG36 RAS | GERMANY | 0–0 | Treat MG36 RAS as a German HK MG36/G36-family rail-equipped configuration. |
| 669 | MG43 | GERMANY | 2001–0 | Interpret JA2 HK MG43 as the early MG43 designation of the German HK MG4 family; approximate start 2001. |
| 688 | Cobray M11/9 | USA | 0–0 | Treat Cobray M11/9 as the US-made SWD/Cobray MAC-pattern commercial variant represented by the JA2 name. |
| 695 | Varjag | RUSSIA | 0–0 | Treat MP-445 Varjag as a Russian Izhevsk/MP-series pistol concept; exact serial-production status is not important for gameplay. |
| 717 | P226R .40 | USA|GERMANY | 0–0 | Treat rail-era .40 P226 as a SIG Sauer Germany/USA production-family weapon. |
| 719 | SIG Pro | SWITZERLAND|GERMANY | 1999–0 | SIG Pro is a Swiss-origin design produced by SIG Sauer in Germany; 1999 is the approximate production start. |
| 729 | SSG-P1 | AUSTRIA | 0–0 | Treat Steyr SSG-P1 as an Austrian Steyr SSG-family precision rifle; exact suffix provenance is not required. |
| 731 | Street Sweeper | USA | 1989–1993 | Interpret 'Street Sweeper' specifically as the US SWD/Cobray copy of the Striker, marketed 1989-1993. |
| 754 | MP-233B | RUSSIA | 0–0 | Treat Baikal MP-233B as a Russian Baikal/Izhmash-family shotgun; exact variant production dates are omitted. |
| 764 | CMMG 7.3 | USA | 0–0 | CMMG is treated as the US manufacturer for this obscure JA2-specific CMMG 7.3 configuration; year left unknown. |
| 770 | Encore | USA | 0–0 | Treat Thompson/Center Encore .454 Casull configuration as a US T/C commercial pistol variant; exact chambering introduction date omitted. |
| 777 | Benelli R-1 | ITALY | 0–0 | Treat Benelli R1 .300 WinMag as an Italian Benelli commercial rifle; exact production start omitted. |
| 784 | Mauser M-03 | GERMANY | 2003–0 | Mauser M03 is a German hunting-rifle system introduced in 2003. |
| 785 | AKMSU | SOVIET_UNION | 0–0 | Treat AKMSU as a Soviet AKMS-derived compact variant for gameplay purposes despite disputed formal designation. |
| 787 | SCAR-H SV | BELGIUM|USA | 0–0 | Treat JA2 SCAR SV/WP/6.8 configurations as FN SCAR-family derivatives; use Belgian FN design plus US SCAR-program manufacture, without claiming exact factory submodels. |
| 788 | SCAR-L SV | BELGIUM|USA | 0–0 | Treat JA2 SCAR SV/WP/6.8 configurations as FN SCAR-family derivatives; use Belgian FN design plus US SCAR-program manufacture, without claiming exact factory submodels. |
| 790 | SCAR-WP CQC | BELGIUM|USA | 0–0 | Treat JA2 SCAR SV/WP/6.8 configurations as FN SCAR-family derivatives; use Belgian FN design plus US SCAR-program manufacture, without claiming exact factory submodels. |
| 791 | SCAR-WP SV | BELGIUM|USA | 0–0 | Treat JA2 SCAR SV/WP/6.8 configurations as FN SCAR-family derivatives; use Belgian FN design plus US SCAR-program manufacture, without claiming exact factory submodels. |
| 792 | SCAR-68 CQC | BELGIUM|USA | 0–0 | Treat JA2 SCAR SV/WP/6.8 configurations as FN SCAR-family derivatives; use Belgian FN design plus US SCAR-program manufacture, without claiming exact factory submodels. |
| 793 | SCAR-68 SV | BELGIUM|USA | 0–0 | Treat JA2 SCAR SV/WP/6.8 configurations as FN SCAR-family derivatives; use Belgian FN design plus US SCAR-program manufacture, without claiming exact factory submodels. |
| 796 | M4A3 | USA | 0–0 | Treat Bushmaster M4A3 6.8 SPC as a US Bushmaster commercial M4-family configuration; exact catalog years omitted. |
| 797 | XCR-1 | USA | 2006–0 | Robinson XCR is a US multi-caliber rifle family including 6.8 SPC; approximate market production start 2006. |
| 798 | Luger P-08 | GERMANY_PRE_1949 | 1908–1942 | Treat P-08 as the standard German Luger service-pistol production era; 1908-1942 is a gameplay-oriented production window. |
| 799 | P226 SAS | USA | 0–0 | Treat P226 SAS as a US-market SIG Sauer SAS treatment of the P226 family; exact SAS introduction date omitted. |
| 800 | P226 SAS .40 | USA | 0–0 | Treat P226 SAS .40 as a US-market SIG Sauer SAS treatment; exact SAS production dates omitted. |
| 897 | M21 EBR | USA | 0–0 | Treat JA2 M21 EBR as a US M21/M14 action in an EBR-style chassis; exact commercial/custom build date omitted. |
| 900 | Pro II | USA | 0–0 | Treat Kimber Eclipse Pro II as a US Kimber commercial 1911 variant; exact first/last production years omitted. |
| 1065 | AUG-A3 | AUSTRIA | 0–0 | Treat JA2 6.8 SPC AUG-A3 as an Austrian Steyr AUG-family conversion; exact 6.8 factory status is not required. |
| 1074 | HEZI SM-1 | ISRAEL | 0–0 | HEZI SM-1 is identified as an Israeli Advanced Combat Systems M1-carbine conversion; exact production dates omitted. |
| 1179 | SIG MP41/44 | SWITZERLAND | 1941–1942 | JA2 label 'SIG MP41/44' is interpreted as the rare Swiss SIG MP41 family rather than the W+F Furrer MP41/44; use 1941-1942 as best-fit limited-production years. |
| 1195 | MC51 | UNITED_KINGDOM | 1990–0 | Treat FR Ordnance MC51 as the UK-built G3 conversion supplied for British special-forces trials around 1990; exact production end omitted. |
| 1201 | SL8 RAS | GERMANY | 1998–0 | Treat SL8 RAS as a railed German HK SL8 configuration; inherit the base SL8's late-1998 production start. |
| 1333 | AR57 11" | USA | 2008–0 | Treat 11-inch AR57 as a US AR57-family configuration; use the family-level 2008 production-era start. |
| 1334 | AR57 6"-S | USA | 2008–0 | Treat 6-inch silenced AR57 as a US AR57-family/custom configuration; use the family-level 2008 production-era start. |

## Remaining ambiguous rows

- **779 S&O Shorty:** Still genuinely opaque: JA2 'S&O Shorty' is a .300 WinMag straight-pull rifle, but no reliable manufacturer/model match was found. Leave runtime metadata zero until someone recognizes it.
