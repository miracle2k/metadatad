#!/usr/bin/env python

import sys
from datetime import datetime
import mutagen, mutagen.mp3, mutagen.easyid3, mutagen.id3

import db


# Extend mutagen with some missing stuff
mutagen.easyid3.EasyID3.RegisterTextKey('grouping', 'TIT1')
def RegisterCOMMKey(id3, key, desc):
    """Register a user-defined commment key.

    Something which mutagen can't do by itself.
    """
    frameid = "COMM:%s:'eng'" % desc
    def getter(id3, key):
        return list(id3[frameid])

    def setter(id3, key, value):
        try:
            frame = id3[frameid]
        except KeyError:
            enc = 0
            # Store 8859-1 if we can, per MusicBrainz spec.
            for v in value:
                if max(v) > u'\x7f':
                    enc = 3
            id3.add(mutagen.id3.COMM(
                encoding=enc, text=value, desc=desc, lang='eng'))
        else:
            frame.text = value

    def deleter(id3, key):
        del(id3[frameid])

    id3.RegisterKey(key, getter, setter, deleter)
RegisterCOMMKey(mutagen.easyid3.EasyID3, 'occasion', 'Songs-DB_Occasion', )
RegisterCOMMKey(mutagen.easyid3.EasyID3, 'songsdb-custom1', 'Songs-DB_Custom1')
RegisterCOMMKey(mutagen.easyid3.EasyID3, 'songsdb-custom2', 'Songs-DB_Custom2')
RegisterCOMMKey(mutagen.easyid3.EasyID3, 'songsdb-custom3', 'Songs-DB_Custom3')


# Allowed tags for different metadata fields.
# From the picard lastfm plus plugin.
FILTER = {}
FILTER["major"] = u"audiobooks, blues, classic rock, classical, country, dance, electronica, folk, hip-hop, indie, jazz, kids, metal, pop, punk, reggae, rock, soul, trance"
FILTER["minor"] = u"2 tone, a cappella, abstract hip-hop, acid, acid jazz, acid rock, acoustic, acoustic guitar, acoustic rock, adult alternative, adult contemporary, alternative, alternative country, alternative folk, alternative metal, alternative pop, alternative rock, ambient, anti-folk, art rock, atmospheric, aussie hip-hop, avant-garde, ballads, baroque, beach, beats, bebop, big band, blaxploitation, blue-eyed soul, bluegrass, blues rock, boogie rock, boogie woogie, bossa nova, breakbeat, breaks, brit pop, brit rock, british invasion, broadway, bubblegum pop, cabaret, calypso, cha cha, choral, christian rock, classic country, classical guitar, club, college rock, composers, contemporary country, contemporary folk, country folk, country pop, country rock, crossover, dance pop, dancehall, dark ambient, darkwave, delta blues, dirty south, disco, doo wop, doom metal, downtempo, dream pop, drum and bass, dub, dub reggae, dubstep, east coast rap, easy listening, electric blues, electro, electro pop, elevator music, emo, emocore, ethnic, eurodance, europop, experimental, fingerstyle, folk jazz, folk pop, folk punk, folk rock, folksongs, free jazz, french rap, funk, funk metal, funk rock, fusion, g-funk, gaelic, gangsta rap, garage, garage rock, glam rock, goa trance, gospel, gothic, gothic metal, gothic rock, gregorian, groove, grunge, guitar, happy hardcore, hard rock, hardcore, hardcore punk, hardcore rap, hardstyle, heavy metal, honky tonk, horror punk, house, humour, hymn, idm, indie folk, indie pop, indie rock, industrial, industrial metal, industrial rock, instrumental, instrumental hip-hop, instrumental rock, j-pop, j-rock, jangle pop, jazz fusion, jazz vocal, jungle, latin, latin jazz, latin pop, lounge, lovers rock, lullaby, madchester, mambo, medieval, melodic rock, minimal, modern country, modern rock, mood music, motown, neo-soul, new age, new romantic, new wave, noise, northern soul, nu metal, old school rap, opera, orchestral, philly soul, piano, political reggae, polka, pop life, pop punk, pop rock, pop soul, post punk, post rock, power pop, progressive, progressive rock, psychedelic, psychedelic folk, psychedelic punk, psychedelic rock, psychobilly, psytrance, punk rock, quiet storm, r&b, ragga, rap, rap metal, reggae pop, reggae rock, rock and roll, rock opera, rockabilly, rocksteady, roots, roots reggae, rumba, salsa, samba, screamo, shock rock, shoegaze, ska, ska punk, smooth jazz, soft rock, southern rock, space rock, spoken word, standards, stoner rock, surf rock, swamp rock, swing, symphonic metal, symphonic rock, synth pop, tango, techno, teen pop, thrash metal, traditional country, traditional folk, tribal, trip-hop, turntablism, underground, underground hip-hop, underground rap, urban, vocal trance, waltz, west coast rap, western swing, world, world fusion"
FILTER["country"] = u"african, american, arabic, australian, austrian, belgian, brazilian, british, canadian, caribbean, celtic, chinese, cuban, danish, dutch, eastern europe, egyptian, estonian, european, finnish, french, german, greek, hawaiian, ibiza, icelandic, indian, iranian, irish, island, israeli, italian, jamaican, japanese, korean, mexican, middle eastern, new zealand, norwegian, oriental, polish, portuguese, russian, scandinavian, scottish, southern, spanish, swedish, swiss, thai, third world, turkish, welsh, western"
FILTER["city"] = u"acapulco, adelaide, amsterdam, athens, atlanta, atlantic city, auckland, austin, bakersfield, bali, baltimore, bangalore, bangkok, barcelona, barrie, beijing, belfast, berlin, birmingham, bogota, bombay, boston, brasilia, brisbane, bristol, brooklyn, brussels, bucharest, budapest, buenos aires, buffalo, calcutta, calgary, california, cancun, caracas, charlotte, chicago, cincinnati, cleveland, copenhagen, dallas, delhi, denver, detroit, dublin, east coast, edmonton, frankfurt, geneva, glasgow, grand rapids, guadalajara, halifax, hamburg, hamilton, helsinki, hong kong, houston, illinois, indianapolis, istanbul, jacksonville, kansas city, kiev, las vegas, leeds, lisbon, liverpool, london, los angeles, louisville, madrid, manchester, manila, marseille, mazatlan, melbourne, memphis, mexico city, miami, michigan, milan, minneapolis, minnesota, mississippi, monterrey, montreal, munich, myrtle beach, nashville, new jersey, new orleans, new york, new york city, niagara falls, omaha, orlando, oslo, ottawa, palm springs, paris, pennsylvania, perth, philadelphia, phoenix, phuket, pittsburgh, portland, puebla, raleigh, reno, richmond, rio de janeiro, rome, sacramento, salt lake city, san antonio, san diego, san francisco, san jose, santiago, sao paulo, seattle, seoul, shanghai, sheffield, spokane, stockholm, sydney, taipei, tampa, texas, tijuana, tokyo, toledo, toronto, tucson, tulsa, vancouver, victoria, vienna, warsaw, wellington, westcoast, windsor, winnipeg, zurich"
FILTER["mood"] = u"angry, bewildered, bouncy, calm, cheerful, chill, cold, complacent, crazy, crushed, cynical, depressed, dramatic, dreamy, drunk, eclectic, emotional, energetic, envious, feel good, flirty, funky, groovy, happy, haunting, healing, high, hopeful, hot, humorous, inspiring, intense, irritated, laidback, lonely, lovesongs, meditation, melancholic, melancholy, mellow, moody, morose, passionate, peace, peaceful, playful, pleased, positive, quirky, reflective, rejected, relaxed, retro, sad, sentimental, sexy, silly, smooth, soulful, spiritual, suicidal, surprised, sympathetic, trippy, upbeat, uplifting, weird, wild, yearning"
FILTER["decade"] = u"1800s, 1810s, 1820s, 1830s, 1980s, 1850s, 1860s, 1870s, 1880s, 1890s, 1900s, 1910s, 1920s, 1930s, 1940s, 1950s, 1960s, 1970s, 1980s, 1990s, 2000s"
FILTER["year"] = u"1801, 1802, 1803, 1804, 1805, 1806, 1807, 1808, 1809, 1810, 1811, 1812, 1813, 1814, 1815, 1816, 1817, 1818, 1819, 1820, 1821, 1822, 1823, 1824, 1825, 1826, 1827, 1828, 1829, 1830, 1831, 1832, 1833, 1834, 1835, 1836, 1837, 1838, 1839, 1840, 1841, 1842, 1843, 1844, 1845, 1846, 1847, 1848, 1849, 1850, 1851, 1852, 1853, 1854, 1855, 1856, 1857, 1858, 1859, 1860, 1861, 1862, 1863, 1864, 1865, 1866, 1867, 1868, 1869, 1870, 1871, 1872, 1873, 1874, 1875, 1876, 1877, 1878, 1879, 1880, 1881, 1882, 1883, 1884, 1885, 1886, 1887, 1888, 1889, 1890, 1891, 1892, 1893, 1894, 1895, 1896, 1897, 1898, 1899, 1900, 1901, 1902, 1903, 1904, 1905, 1906, 1907, 1908, 1909, 1910, 1911, 1912, 1913, 1914, 1915, 1916, 1917, 1918, 1919, 1920, 1921, 1922, 1923, 1924, 1925, 1926, 1927, 1928, 1929, 1930, 1931, 1932, 1933, 1934, 1935, 1936, 1937, 1938, 1939, 1940, 1941, 1942, 1943, 1944, 1945, 1946, 1947, 1948, 1949, 1950, 1951, 1952, 1953, 1954, 1955, 1956, 1957, 1958, 1959, 1960, 1961, 1962, 1963, 1964, 1965, 1966, 1967, 1968, 1969, 1970, 1971, 1972, 1973, 1974, 1975, 1976, 1977, 1978, 1979, 1980, 1981, 1982, 1983, 1984, 1985, 1986, 1987, 1988, 1989, 1990, 1991, 1992, 1993, 1994, 1995, 1996, 1997, 1998, 1999, 2000, 2001, 2002, 2003, 2004, 2005, 2006, 2007, 2008, 2009, 2010, 2011, 2012, 2013, 2014, 2015, 2016, 2017, 2018, 2019, 2020"
FILTER["occasion"] = u"background, birthday, breakup, carnival, chillout, christmas, death, dinner, drinking, driving, graduation, halloween, hanging out, heartache, holiday, late night, love, new year, party, protest, rain, rave, romantic, sleep, spring, summer, sunny, twilight, valentine, wake up, wedding, winter, work"
FILTER["category"] = u"animal songs, attitude, autumn, b-side, ballad, banjo, bass, beautiful, body parts, bootlegs, brass, cafe del mar, chamber music, clarinet, classic, classic tunes, compilations, covers, cowbell, deceased, demos, divas, dj, drugs, drums, duets, field recordings, female, female vocalists, film score, flute, food, genius, girl group, great lyrics, guitar solo, guitarist, handclaps, harmonica, historical, horns, hypnotic, influential, insane, jam, keyboard, legends, life, linedance, live, loved, lyricism, male, male vocalists, masterpiece, melodic, memories, musicals, nostalgia, novelty, number songs, old school, oldie, oldies, one hit wonders, orchestra, organ, parody, poetry, political, promos, radio programs, rastafarian, remix, samples, satire, saxophone, showtunes, sing-alongs, singer-songwriter, slide guitar, solo instrumentals, songs with names, soundtracks, speeches, stories, strings, stylish, synth, title is a full sentence, top 40, traditional, trumpet, unique, unplugged, violin, virtuoso, vocalization, vocals"
for key, list in FILTER.items():
    FILTER[key] = map(unicode.strip, list.split(','))
del key, list

# Tag translations
# From the picard lastfm plus plugin.
TRANSLATIONS = "00s, 2000s\n10s, 1910s\n1920's, 1920s\n1930's, 1930s\n1940's, 1940s\n1950's, 1950s\n1960's, 1960s\n1970's, 1970s\n1980's, 1980s\n1990's, 1990s\n2-tone, 2 tone\n20's, 1920s\n2000's, 2000s\n2000s, 2000s\n20s, 1920s\n20th century classical, classical\n30's, 1930s\n30s, 1930s\n3rd wave ska revival, ska\n40's, 1940s\n40s, 1940s\n50's, 1950s\n50s, 1950s\n60's, 1960s\n60s, 1960s\n70's, 1970s\n70s, 1970s\n80's, 1980s\n80s, 1980s\n90's, 1990s\n90s, 1990s\na capella, a cappella\nabstract-hip-hop, hip-hop\nacapella, a cappella\nacid-rock, acid rock\nafrica, african\naggresive, angry\naggressive, angry\nalone, lonely\nalready-dead, deceased\nalt rock, alternative rock\nalt-country, alternative country\nalternative  punk, punk\nalternative dance, dance\nalternative hip-hop, hip-hop\nalternative pop-rock, pop rock\nalternative punk, punk\nalternative rap, rap\nambient-techno, ambient\namericain, american\namericana, american\nanimal-songs, animal songs\nanimals, animal songs\nanti-war, protest\narena rock, rock\natmospheric-drum-and-bass, drum and bass\nau, australian\naussie hip hop, aussie hip-hop\naussie hiphop, aussie hip-hop\naussie rock, australian\naussie, australian\naussie-rock, rock\naustralia, australian\naustralian aboriginal, world\naustralian country, country\naustralian hip hop, aussie hip-hop\naustralian hip-hop, aussie hip-hop\naustralian rap, aussie hip-hop\naustralian rock, rock\naustralian-music, australian\naustralianica, australian\naustralicana, australian\naustria, austrian\navantgarde, avant-garde\nbakersfield-sound, bakersfield\nbaroque pop, baroque\nbeach music, beach\nbeat, beats\nbelgian music, belgian\nbelgian-music, belgian\nbelgium, belgian\nbhangra, indian\nbig beat, beats\nbigbeat, beats\nbittersweet, cynical\nblack metal, doom metal\nblue, sad\nblues guitar, blues\nblues-rock, blues rock\nbluesrock, blues rock\nbollywood, indian\nboogie, boogie woogie\nboogiewoogieflu, boogie woogie\nbrazil, brazilian\nbreakbeats, breakbeat\nbreaks artists, breakbeat\nbrit, british\nbrit-pop, brit pop\nbrit-rock, brit rock\nbritish blues, blues\nbritish punk, punk\nbritish rap, rap\nbritish rock, brit rock\nbritish-folk, folk\nbritpop, brit pop\nbritrock, brit rock\nbroken beat, breakbeat\nbrutal-death-metal, doom metal\nbubblegum, bubblegum pop\nbuddha bar, chillout\ncalming, relaxed\ncanada, canadian\ncha-cha, cha cha\ncha-cha-cha, cha cha\nchicago blues, blues\nchildren, kids\nchildrens music, kids\nchildrens, kids\nchill out, chillout\nchill-out, chillout\nchilled, chill\nchillhouse, chill\nchillin, hanging out\nchristian, gospel\nchina, chinese\nclasica, classical\nclassic blues, blues\nclassic jazz, jazz\nclassic metal, metal\nclassic pop, pop\nclassic punk, punk\nclassic roots reggae, roots reggae\nclassic soul, soul\nclassic-hip-hop, hip-hop\nclassical crossover, classical\nclassical music, classical\nclassics, classic tunes\nclassique, classical\nclub-dance, dance\nclub-house, house\nclub-music, club\ncollegiate acappella, a cappella\ncomedy rock, humour\ncomedy, humour\ncomposer, composers\nconscious reggae, reggae\ncontemporary classical, classical\ncontemporary gospel, gospel\ncontemporary jazz, jazz\ncontemporary reggae, reggae\ncool-covers, covers\ncountry folk, country\ncountry soul, country\ncountry-divas, country\ncountry-female, country\ncountry-legends, country\ncountry-pop, country pop\ncountry-rock, country rock\ncover, covers\ncover-song, covers\ncover-songs, covers\ncowboy, country\ncowhat-fav, country\ncowhat-hero, country\ncuba, cuban\ncyberpunk, punk\nd'n'b, drum and bass\ndance party, party\ndance-punk, punk\ndance-rock, rock\ndancefloor, dance\ndancehall-reggae, dancehall\ndancing, dance\ndark-psy, psytrance\ndark-psytrance, psytrance\ndarkpsy, dark ambient\ndeath metal, doom metal\ndeathcore, thrash metal\ndeep house, house\ndeep-soul, soul\ndeepsoul, soul\ndepressing, depressed\ndepressive, depressed \ndeutsch, german\ndisco-funk, disco\ndisco-house, disco\ndiva, divas\ndj mix, dj\ndnb, drum and bass\ndope, drugs\ndownbeat, downtempo\ndream dance, trance\ndream trance, trance\ndrill 'n' bass, drum and bass\ndrill and bass, drum and bass\ndrill n bass, drum and bass\ndrill-n-bass, drum and bass\ndrillandbass, drum and bass\ndrinking songs, drinking\ndriving-music, driving\ndrum 'n' bass, drum and bass\ndrum n bass, drum and bass\ndrum'n'bass, drum and bass\ndrum, drums\ndrum-n-bass, drum and bass\ndrumandbass, drum and bass\ndub-u, dub\ndub-u-dub, dub\ndub-wise, dub\nduet, duets\nduo, duets\ndutch artists, dutch\ndutch rock, rock\ndutch-bands, dutch\ndutch-sound, dutch\nearly reggae, reggae\neasy, easy listening\negypt, egyptian\neighties, 1980s\nelectro dub, electro\nelectro funk, electro\nelectro house, house\nelectro rock, electro\nelectro-pop, electro\nelectroclash, electro\nelectrofunk, electro\nelectrohouse, house\nelectronic, electronica\nelectronic-rock, rock\nelectronicadance, dance\nelectropop, electro pop\nelectropunk, punk\nelegant, stylish\nelektro, electro\nelevator, elevator music\nemotive, emotional\nenergy, energetic\nengland, british\nenglish, british\nenraged, angry\nepic-trance, trance\nethnic fusion, ethnic\neuro-dance, eurodance\neuro-pop, europop\neuro-trance, trance\neurotrance, trance\neurovision, eurodance\nexperimental-rock, experimental\nfair dinkum australian mate, australian\nfeel good music, feel good\nfeelgood, feel good\nfemale artists, female\nfemale country, country\nfemale fronted, female\nfemale singers, female\nfemale vocalist, female vocalists\nfemale-vocal, female vocalists\nfemale-vocals, female vocalists\nfemale-voices, female vocalists\nfield recording, field recordings\nfilm, film score\nfilm-score, film score\nfingerstyle guitar, fingerstyle\nfinland, finnish\nfinnish-metal, metal\nflamenco rumba, rumba\nfolk-jazz, folk jazz\nfolk-pop, folk pop\nfolk-rock, folk rock\nfolkrock, folk rock\nfrancais, french\nfrance, french\nfreestyle, electronica\nfull on, energetic\nfull-on, energetic\nfull-on-psychedelic-trance, psytrance\nfull-on-trance, trance\nfullon, intense \nfuneral, death\nfunky breaks, breaks\nfunky house, house\nfunny, humorous\ngabber, hardcore\ngeneral pop, pop\ngeneral rock, rock\ngentle, smooth\ngermany, german\ngirl-band, girl group\ngirl-group, girl group\ngirl-groups, girl group\ngirl-power, girl group\ngirls, girl group\nglam metal, glam rock\nglam, glam rock\ngloomy, depressed\ngoa classic, goa trance\ngoa, goa trance\ngoa-psy-trance, psytrance\ngoatrance, trance\ngolden oldies, oldies\ngoth rock, gothic rock\ngoth, gothic\ngothic doom metal, gothic metal\ngreat-lyricists, great lyrics\ngreat-lyrics, great lyrics\ngrime, dubstep\ngregorian chant, gregorian\ngrock 'n' roll, rock and roll\ngroovin, groovy\ngrunge rock, grunge\nguitar god, guitar\nguitar gods, guitar\nguitar hero, guitar\nguitar rock, rock\nguitar-solo, guitar solo\nguitar-virtuoso, guitarist\nhair metal, glam rock\nhanging-out, hanging out\nhappiness, happy\nhappy thoughts, happy\nhard dance, dance\nhard house, house\nhard-trance, trance\nhardcore-techno, techno\nhawaii, hawaiian\nheartbreak, heartache\nheavy rock, hard rock\nhilarious, humorous\nhip hop, hip-hop\nhip-hop and rap, hip-hop\nhip-hoprap, hip-hop\nhiphop, hip-hop\nhippie, stoner rock\nhope, hopeful\nhorrorcore, thrash metal\nhorrorpunk, horror punk\nhumor, humour\nindia, indian\nindie electronic, electronica\nindietronica, electronica\ninspirational, inspiring\ninstrumental pop, instrumental \niran, iranian\nireland, irish\nisrael, israeli\nitaly, italian\njam band, jam\njamaica, jamaican\njamaican ska, ska\njamaician, jamaican\njamaican-artists, jamaican\njammer, jam\njazz blues, jazz\njazz funk, jazz\njazz hop, jazz\njazz piano, jazz\njpop, j-pop\njrock, j-rock\njazz rock, jazz\njazzy, jazz\njump blues, blues\nkiwi, new zealand\nlaid back, easy listening\nlatin rock, latin\nlatino, latin\nle rap france, french rap\nlegend, legends\nlegendary, legends\nlekker ska, ska\nlions-reggae-dancehall, dancehall\nlistless, irritated\nlively, energetic\nlove metal, metal\nlove song, romantic\nlove-songs, lovesongs\nlovely, beautiful\nmade-in-usa, american\nmakes me happy, happy\nmale country, country\nmale groups, male\nmale rock, male\nmale solo artists, male\nmale vocalist, male vocalists\nmale-vocal, male vocalists\nmale-vocals, male vocalists\nmarijuana, drugs\nmelancholic days, melancholy\nmelodic death metal, doom metal\nmelodic hardcore, hardcore\nmelodic metal, metal\nmelodic metalcore, metal\nmelodic punk, punk\nmelodic trance, trance\nmetalcore, thrash metal\nmetro downtempo, downtempo\nmetro reggae, reggae\nmiddle east, middle eastern\nminimal techno, techno\nmood, moody\nmorning, wake up\nmoses reggae, reggae\nmovie, soundtracks\nmovie-score, soundtracks\nmovie-score-composers, composers\nmovie-soundtrack, soundtracks\nmusical, musicals\nmusical-theatre, musicals\nneder rock, rock \nnederland, dutch\nnederlands, dutch\nnederlandse-muziek, dutch\nnederlandstalig, dutch\nnederpop, pop\nnederrock, rock\nnederska, ska\nnedertop, dutch\nneo prog, progressive\nneo progressive rock, progressive rock\nneo progressive, progressive\nneo psychedelia, psychedelic\nneo soul, soul\nnerd rock, rock\nnetherlands, dutch\nneurofunk, funk\nnew rave, rave\nnew school breaks, breaks \nnew school hardcore, hardcore\nnew traditionalist country, traditional country\nnice elevator music, elevator music\nnight, late night\nnight-music, late night\nnoise pop, pop\nnoise rock, rock\nnorway, norwegian\nnostalgic, nostalgia\nnu breaks, breaks\nnu jazz, jazz\nnu skool breaks, breaks \nnu-metal, nu metal\nnumber-songs, number songs\nnumbers, number songs\nnumetal, metal\nnz, new zealand\nold country, country\nold school hardcore, hardcore \nold school hip-hop, hip-hop\nold school reggae, reggae\nold school soul, soul\nold-favorites, oldie\nold-skool, old school\nold-timey, oldie\noldschool, old school\none hit wonder, one hit wonders\noptimistic, positive\noutlaw country, country\noz hip hop, aussie hip-hop\noz rock, rock\noz, australian\nozzie, australian\npancaribbean, caribbean\nparodies, parody\nparty-groovin, party\nparty-music, party\nparty-time, party\npiano rock, piano\npolitical punk, punk\npolitical rap, rap\npool party, party\npop country, country pop\npop music, pop\npop rap, rap\npop-rap, rap\npop-rock, pop rock\npop-soul, pop soul\npoprock, pop rock\nportugal, portuguese\npositive-vibrations, positive\npost grunge, grunge\npost hardcore, hardcore\npost-grunge, grunge\npost-hardcore, hardcore\npost-punk, post punk\npost-rock, post rock\npostrock, post rock\npower ballad, ballad\npower ballads, ballad\npower metal, metal\nprog rock, progressive rock\nprogressive breaks, breaks\nprogressive house, house\nprogressive metal, nu metal\nprogressive psytrance, psytrance \nprogressive trance, psytrance\nproto-punk, punk\npsy, psytrance\npsy-trance, psytrance\npsybient, ambient\npsych folk, psychedelic folk\npsych, psytrance\npsychadelic, psychedelic\npsychedelia, psychedelic\npsychedelic pop, psychedelic\npsychedelic trance, psytrance\npsychill, psytrance\npsycho, insane\npsytrance artists, psytrance\npub rock, rock \npunk blues, punk\npunk caberet, punk\npunk favorites, punk \npunk pop, punk\npunk revival, punk\npunkabilly, punk\npunkrock, punk rock\nqueer, quirky\nquiet, relaxed\nr and b, r&b\nr'n'b, r&b\nr-n-b, r&b\nraggae, reggae\nrap and hip-hop, rap\nrap hip-hop, rap\nrap rock, rap\nrapcore, rap metal\nrasta, rastafarian\nrastafari, rastafarian\nreal hip-hop, hip-hop\nreegae, reggae\nreggae and dub, reggae\nreggae broeder, reggae\nreggae dub ska, reggae\nreggae roots, roots reggae\nreggae-pop, reggae pop\nreggea, reggae\nrelax, relaxed\nrelaxing, relaxed\nrhythm and blues, r&b\nrnb, r&b\nroad-trip, driving\nrock ballad, ballad\nrock ballads, ballad\nrock n roll, rock and roll\nrock pop, pop rock\nrock roll, rock and roll\nrock'n'roll, rock and roll\nrock-n-roll, rock and roll\nrocknroll, rock and roll\nrockpop, pop rock\nromance, romantic\nromantic-tension, romantic\nroots and culture, roots\nroots rock, rock\nrootsreggae, roots reggae \nrussian alternative, russian\nsad-songs, sad\nsample, samples\nsaturday night, party\nsax, saxophone\nscotland, scottish\nseden, swedish\nsensual, passionate\nsing along, sing-alongs\nsing alongs, sing-alongs\nsing-along, sing-alongs\nsinger-songwriters, singer-songwriter\nsingersongwriter, singer-songwriter\nsixties, 1960s\nska revival, ska \nska-punk, ska punk\nskacore, ska\nskate punk, punk\nskinhead reggae, reggae\nsleepy, sleep\nslow jams, slow jam\nsmooth soul, soul\nsoft, smooth\nsolo country acts, country\nsolo instrumental, solo instrumentals\nsoothing, smooth\nsoulful drum and bass, drum and bass\nsoundtrack, soundtracks\nsouth africa, african\nsouth african, african\nsouthern rap, rap\nsouthern soul, soul\nspain, spanish\nspeed metal, metal\nspeed, drugs\nspirituals, spiritual\nspliff, drugs\nstoner, stoner rock\nstreet punk, punk\nsuicide, death\nsuicide, suicidal\nsummertime, summer\nsun-is-shining, sunny\nsunshine pop, pop\nsuper pop, pop\nsurf, surf rock\nswamp blues, swamp rock\nswamp, swamp rock\nsweden, swedish\nswedish metal, metal\nsymphonic power metal, symphonic metal\nsynthpop, synth pop\ntexas blues, blues\ntexas country, country\nthird wave ska revival, ska\nthird wave ska, ska\ntraditional-ska, ska\ntrancytune, trance\ntranquility, peaceful\ntribal house, tribal\ntribal rock, tribal\ntrip hop, trip-hop\ntriphop, trip-hop\ntwo tone, 2 tone\ntwo-tone, 2 tone\nuk hip-hop, hip-hop\nuk, british\nunited kingdom, british\nunited states, american\nuntimely-death, deceased\nuplifting trance, trance\nus, american\nusa, american\nvocal house, house\nvocal jazz, jazz vocal\nvocal pop, pop\nvocal, vocals\nwales, welsh\nweed, drugs\nwest-coast, westcoast\nworld music, world\nxmas, christmas\n"
TRANSLATIONS = dict(map(lambda s: (s[0].strip(), s[1].strip()),
                        [t.split(',') for t in TRANSLATIONS.strip().split('\n')]))

def replace_translations(tags):
    """In the incoming dict of tag -> popularity values, normalize
    certain tag names using a translation mapping, and keep track
    of the popularity accordingly.
    """
    if not tags:
        return tags
    result = {}
    for tag, count in tags.items():
        if tag in TRANSLATIONS:
            tag_to_use = TRANSLATIONS[tag]
        else:
            tag_to_use = tag
        result.setdefault(tag_to_use, 0)
        result[tag_to_use] += count
    # The incoming counts where probably already percentile-normalized
    # (coming from last.fm), make them again percentage values.
    maxcount = float(max(result.values()))
    result = [(k, v/maxcount*100) for k, v in result.items()]
    return result

def matches_list(s, lst):
    """See if ``s`` is in the filter list ``lst``.
    """
    if s in lst:
        return True
    for item in lst:
        if '*' in item:
            if re.match(re.escape(item).replace(r'\*', '.*?'), s):
                return True
    return False


def apply_factor(tags, f):
    """Adjust the weight of all the tags in the list."""
    return [(t, w*f) for t, w in tags]


# Different tag types recognized by choose_tags().
NORMAL_TAG = 0
EXTENSION_AUTHOR_TAG = 1
NORMAL_AUTHOR_TAG = 2


def choose_tags(tags, cfg):
    """Given the given list of tags, choose which to use for which
    metadata field.

    This could was taken from the Picard last.fm plus plugin.

    Input format of ``tags`` is a list of 2-tuples in the form of
    (tagname, (weight, type)).

    Output format is a dict in the form of:

        {'category/tags': ['female vocalists', 'oldies', 'classic', 'female'],
         'city/tags': ['stockholm'],
         'country/tags': ['swedish'],
         'decade/tags': ['1970s'],
         'major/tags': ['pop'],
         'mood/tags': ['happy', 'cheerful', 'upbeat', 'retro'],
         'occasion/tags': ['party', 'love', 'driving', 'romantic'],
         'year2/tags': ['1975']}
    """
    # Remembers the weight of the previous tag (remember we process
    # the list of tags in ordered form). We use this to refuse tags
    # if their weight drops too much in a single step, indicating
    # a loss in quality. n stands for normal, e for tags only used
    # as a fallback for extension purposes.
    lastw = {"n": False, "e": False}

    # The list of metadata fields we try to assign data to based on
    # the list of tags; different fields are handled differently,
    # this dict stores the modes for each.
    # List: (use sally-tags, use track-tags, use artist-tags, use drop-info,
    #        use minweight, allowed tags, max tags)
    info = {"major"   : [True,  True,  True,  True,  True,  FILTER["major"], cfg["max_group_tags"]],
            "minor"   : [True,  True,  True,  True,  True,  FILTER["minor"], cfg["max_minor_tags"]],
            "country" : [True,  False, True,  False, False, FILTER["country"], 1],
            "city"    : [True,  False, True,  False, False, FILTER["city"], 1],
            "decade"  : [True,  True,  False, False, False, FILTER["decade"], 1],
            "year"    : [True,  True,  False, False, False, FILTER["year"], 1],
            "year2"   : [True,  True,  False, False, False, FILTER["year"], 1],
            "year3"   : [True,  True,  False, False, False, FILTER["year"], 1],
            "mood"    : [True,  True,  True,  False, False, FILTER["mood"], cfg["max_mood_tags"]],
            "occasion": [True,  True,  True,  False, False, FILTER["occasion"], cfg["max_occasion_tags"]],
            "category": [True,  True,  True,  False, False, FILTER["category"], cfg["max_category_tags"]]
           }

    # This will store the result; the tags we intend to keep.
    hold = {"all/tags" : []}

    # Go through list of tags, sorted by popularity in descending order,
    # choosing the most popular tags for each metadata field.
    cmptaginfo = lambda a, b: cmp(a[1][0], b[1][0]) * -1
    tags.sort(cmp=cmptaginfo)
    for tag, [weight, stype] in tags:
        # XXX Should be written properly in the first place
        tag = unicode(tag)

        # Means this is an author tag that should only be used for
        # extending, if there are too few track tags available.
        e = stype == EXTENSION_AUTHOR_TAG
        # Whether track type, or any type of an artist tag
        arttag = stype in (EXTENSION_AUTHOR_TAG, NORMAL_AUTHOR_TAG)

        # Add the tag to the list of tags.
        if not tag in hold["all/tags"]:
            hold["all/tags"].append(tag)

        # Decide if this tag falls below the drop threshold; Note that
        # normal tags, and tags used for extension only, are handled
        # separately, and can use different thresholds.
        drop = not (e and (not lastw['e'] or (lastw['e']-weight) < cfg["max_sally_drop"])) \
               and not (not e and (not lastw['n'] or (lastw['n']-weight) < cfg["max_drop"]))
        if not drop:
            lastw['e' if e else 'n'] = weight

        # Decide whether the tag is below the absolute minumum weight.
        below = (e and weight < cfg["min_sally_weight"]) or \
                (not e and weight < cfg["min_tag_weight"])

        # Go through the list of metadata types ('group'), and find one
        # which will accept this tag.
        for group, opts in info.items():
            # Must be in the list of allowed tags for this group
            if not matches_list(tag, opts[5]):
                continue
            # For some groups...
            # (note we can break because filter lists should not
            # overlap anyway!)
            # ...the tag must have a minimum weight
            if below and opts[4]: break
            # ...the tag must meet a drop threshold
            if drop and opts[3]: break
            # ...extension tags should not be used
            if e and not opts[0]: break
            # ...artists tags should not be used
            if arttag and not opts[2]: break
            # ...track tags should not be used
            if not arttag and not opts[1]: break

            # If we come across a track tag that was already registered
            # as a extension tag, prefer the track version.
            # TODO: Does this mean it is still possible for non-extend
            # artist tags to duplicate track tags?
            if not e and group+"/sally" in hold and tag in hold[group+"/sally"]:
                hold[group+"/sally"].remove(tag)
                hold[group+"/tags"].remove(tag)

            # Keep track of this tag as one we might want to use
            hold.setdefault(group+"/tags", [])
            if not tag in hold[group+"/tags"]:
                hold[group+"/tags"].append(tag)
                # Keep a separate list of extension tags, so we can
                # drop them first, later one.
                if e:
                    hold.setdefault(group+"/sally", [])
                    hold.setdefault(group+"/sally", [])

            # Only ever add a tag to one metadata type.
            break

    # Cut the lists of tags to the requested size
    for group, opts in info.items():
        while len(hold.get(group+"/tags", [])) > opts[6]:
            # remove extension tags first
            if len(hold.get(group+"/sally", [])) > 0:
                deltag = hold[group+"/sally"].pop()
                hold[group+"/tags"].remove(deltag)
            else:
                hold[group+"/tags"].pop()

    # Prepare a nicer result object: Only return the /tags items
    # (which are the tags we have selected), and remove any metadata
    # types which have not received tags.
    del hold['all/tags']
    hold = dict(filter(lambda i: i[1] and i[0].endswith('/tags'), hold.items()))

    return hold


def apply_tags(current, new, cfg):
    # join the information
    joiner = cfg["join_tags_sign"]
    def join_tags(list):
        if joiner and list:
            return [unicode(joiner).join(list)]
        return list

    diff = {}

    def set(from_key, to_tag):
        # from_key may be a key for the 'new' dict, or
        # a list of tags to write.
        if not isinstance(from_key, list):
            new_values = new.get(from_key, [])
        else:
            new_values = from_key
        new_values_written = join_tags(new_values)

        old_values = current.get(to_tag) or []
        if new_values_written != old_values:
            if new_values is None:
                del current[to_tag]
            else:
                current[to_tag] = new_values_written
            diff[to_tag] = (new_values_written, old_values)

    # write the major-tags
    set("major/tags", "grouping")

    # write the decade-tags
    set("decade/tags", "songsdb-custom1")  # TODO: lowercase?
    # TODO: The original last.fm plus plugin uses existing date/originalyear
    # tags to set decade tags if none are found otherwise.

    # write the mood-tags
    set("mood/tags", "mood")

    # country/city tags
    tags = None
    if cfg["use_country_tag"] and cfg["use_city_tag"]:
        tags = new.get("country/tags", []) + new.get("city/tags", [])
    elif cfg["use_country_tag"]:
        tags = "country/tags"
    elif cfg["use_city_tag"]:
        tags = "city/tags"
    if tags:
        set(tags, "songsdb-custom3")

    # write the occasion-tags
    set("occasion/tags", "occasion")

    # write the category-tags
    set("category/tags", "songsdb-custom2")

    # write minor/genre tags - prepend major if requested
    if cfg["apply_major2minor_tag"]:
        set(new.get('major/tags', []) + new.get('minor/tags', []),
            "genre")
    else:
        # just write minor tags, or if none exist, fallback to a copy of
        # the major tags.
        set(new.get('minor/tags', []) or new.get('major/tags', []), "genre")


    # TODO: The year tags aren't really used ...

    return diff


def main():
    assert len(sys.argv) == 1, "Syntax: ./fetchtags.py"
    database = db.Database()

    cfg = {
        # What to do with artist tags:
        #    - True = use them, applying ``artist_weight``.
        #    - False = ignore them.
        #    - 'extend' = use them as a fallback if too few
        #                 tag tags
        'artist_tags': False,
        # Relative weight of artist tags. Not relevant
        #  when in extend mode.
        'artist_weight': 0.8,
        # Number of tags to use.
        'max_group_tags': 1,
        'max_minor_tags': 4,
        'max_mood_tags': 4,
        'max_occasion_tags': 4,
        'max_category_tags': 4,
        # Ignore a tag when it's weight differs more
        # than this drop relative to the next popular one.
        'max_drop': 0.9,
        # A separate drop threshold to use for artist tags
        #  when in extend mode.
        'max_sally_drop': 0.8,
        # Absolute minimum tag weight, for normal tags, and
        # artist tags in extend mode.
        'min_tag_weight': 0.05,
        'min_sally_weight': 0.10,
        # How to join multiple tags.
        'join_tags_sign': u'',
        # Which tags to write at all
        'use_country_tag': True,
        'use_city_tag': True,
        # prepend minor with major tag
        'apply_major2minor_tag': True
    }

    skipped = []
    not_mp3 = []
    no_meta = []
    c = 0
    try:
        for file in database.files.values():
            c += 1
            if c % 2000 == 0:
                print c
                import time
                time.sleep(2)

            if not file.artist or not file.track:
                no_meta.append(file.filename)
                continue

            #if getattr(file, 'last_written', False):
            #    #print '%s already processed' % file.filename
            #    continue

            # Get the artist tags.
            if cfg['artist_tags'] in [True, 'extend']:
                artist_tags = database.artists[file.artist.key()].tags
                artist_tags = replace_translations(artist_tags)
                artist_tags = apply_factor(artist_tags, cfg['artist_weight'])
            else:
                artist_tags = []

            # Get the track tags
            if getattr(file, 'track', False):
                track_tags = database.tracks[file.track.key()].tags
                track_tags = replace_translations(track_tags)
            else:
                track_tags = []

            # Build a single list of tags, in the format expected by
            # choose_tags(). For this, we need to change the second value
            # of an item from ``weight`` to a 2-tuple ``(weight, type)``.
            append_type = lambda tags, type: [(t, (w, type)) for t, w in tags]
            tags = append_type(track_tags, NORMAL_TAG) + \
                   append_type(artist_tags, NORMAL_AUTHOR_TAG \
                                                 if cfg['artist_tags']==True \
                                                 else EXTENSION_AUTHOR_TAG)

            # Figure out which tags to use.
            tags = choose_tags(tags, cfg)

            # Open the file
            try:
                audio = mutagen.File(file.filename, easy=True)
            except Exception, e:
                skipped.append((file.filename, e))
                continue
            if not audio:
                print '%s not valid audio?' % file.filename
                skipped.append((file.filename, 'mutagen-failed'))
                continue
            if not isinstance(audio, mutagen.mp3.EasyMP3):
                not_mp3.append(file.filename)
                print '%s skipped, not mp3' % file.filename
                continue

            print
            print '%s' % file.filename,
            if getattr(file, 'track', False):
                print ' (%s)' % file.track.name
            diff = apply_tags(audio.tags, tags, cfg)
            if diff:
                audio.save()
                file.last_written = datetime.utcnow()

            for key, (new, old) in diff.items():
                if not new:
                    print '  %s: deleted' % key
                    print '     was: %s' % ', '.join(map(lambda a: '"%s"' % a, old))
                elif not old:
                    print '  %s: added' % key
                    print '      is: %s' % ', '.join(map(lambda a: '"%s"' % a, new))
                else:
                    print '  %s: changed' % key
                    print '    from: %s' % ', '.join(map(lambda a: '"%s"' % a, old))
                    print '      to: %s' % ', '.join(map(lambda a: '"%s"' % a, new))
            else:
                print '  no changes'

            # XXX debug: use of artist tags, use of dropped tags
    finally:
        print 'Saving...'
        database.commit()
        database.close()

        print '%s files failed - writing to applytags.failed' % len(skipped)
        with open('applytags.skipped', 'w') as f:
            f.write('\n'.join(map(lambda s: '%s: %s' % s, skipped)))

        print '%s files are not mp3s - writing to applytags.notmp3' % len(not_mp3)
        with open('applytags.notmp3', 'w') as f:
            f.write('\n'.join(not_mp3))

        print '%s files have no artist/track record attached - writing to applytags.nometa' % len(not_mp3)
        with open('applytags.nometa', 'w') as f:
            f.write('\n'.join(no_meta))

main()
