#!/usr/bin/env python3
"""
Generate 100+ realistic airport records for DocumentDB population
"""

def generate_airports():
    """Generate 100+ airport records with realistic data"""
    airports = [
        # North America
        {"iata": "ATL", "icao": "KATL", "name": "Hartsfield-Jackson Atlanta International Airport", "city": "Atlanta", "country": "United States", "latitude": "33.6407", "longitude": "-84.4277", "elevation": 1026, "timezone": "America/New_York"},
        {"iata": "LAX", "icao": "KLAX", "name": "Los Angeles International Airport", "city": "Los Angeles", "country": "United States", "latitude": "33.9425", "longitude": "-118.4081", "elevation": 125, "timezone": "America/Los_Angeles"},
        {"iata": "ORD", "icao": "KORD", "name": "O'Hare International Airport", "city": "Chicago", "country": "United States", "latitude": "41.9742", "longitude": "-87.9073", "elevation": 672, "timezone": "America/Chicago"},
        {"iata": "DFW", "icao": "KDFW", "name": "Dallas/Fort Worth International Airport", "city": "Dallas", "country": "United States", "latitude": "32.8998", "longitude": "-97.0403", "elevation": 607, "timezone": "America/Chicago"},
        {"iata": "DEN", "icao": "KDEN", "name": "Denver International Airport", "city": "Denver", "country": "United States", "latitude": "39.8561", "longitude": "-104.6737", "elevation": 5431, "timezone": "America/Denver"},
        {"iata": "JFK", "icao": "KJFK", "name": "John F. Kennedy International Airport", "city": "New York", "country": "United States", "latitude": "40.6413", "longitude": "-73.7781", "elevation": 13, "timezone": "America/New_York"},
        {"iata": "SFO", "icao": "KSFO", "name": "San Francisco International Airport", "city": "San Francisco", "country": "United States", "latitude": "37.6213", "longitude": "-122.3790", "elevation": 13, "timezone": "America/Los_Angeles"},
        {"iata": "SEA", "icao": "KSEA", "name": "Seattle-Tacoma International Airport", "city": "Seattle", "country": "United States", "latitude": "47.4502", "longitude": "-122.3088", "elevation": 433, "timezone": "America/Los_Angeles"},
        {"iata": "LAS", "icao": "KLAS", "name": "Harry Reid International Airport", "city": "Las Vegas", "country": "United States", "latitude": "36.0840", "longitude": "-115.1537", "elevation": 2181, "timezone": "America/Los_Angeles"},
        {"iata": "MCO", "icao": "KMCO", "name": "Orlando International Airport", "city": "Orlando", "country": "United States", "latitude": "28.4312", "longitude": "-81.3081", "elevation": 96, "timezone": "America/New_York"},
        {"iata": "MIA", "icao": "KMIA", "name": "Miami International Airport", "city": "Miami", "country": "United States", "latitude": "25.7959", "longitude": "-80.2870", "elevation": 8, "timezone": "America/New_York"},
        {"iata": "PHX", "icao": "KPHX", "name": "Phoenix Sky Harbor International Airport", "city": "Phoenix", "country": "United States", "latitude": "33.4352", "longitude": "-112.0101", "elevation": 1135, "timezone": "America/Phoenix"},
        {"iata": "IAH", "icao": "KIAH", "name": "George Bush Intercontinental Airport", "city": "Houston", "country": "United States", "latitude": "29.9902", "longitude": "-95.3368", "elevation": 97, "timezone": "America/Chicago"},
        {"iata": "BOS", "icao": "KBOS", "name": "Boston Logan International Airport", "city": "Boston", "country": "United States", "latitude": "42.3656", "longitude": "-71.0096", "elevation": 20, "timezone": "America/New_York"},
        {"iata": "MSP", "icao": "KMSP", "name": "Minneapolis-St Paul International Airport", "city": "Minneapolis", "country": "United States", "latitude": "44.8848", "longitude": "-93.2223", "elevation": 841, "timezone": "America/Chicago"},
        {"iata": "DTW", "icao": "KDTW", "name": "Detroit Metropolitan Wayne County Airport", "city": "Detroit", "country": "United States", "latitude": "42.2162", "longitude": "-83.3554", "elevation": 645, "timezone": "America/New_York"},
        {"iata": "PHL", "icao": "KPHL", "name": "Philadelphia International Airport", "city": "Philadelphia", "country": "United States", "latitude": "39.8744", "longitude": "-75.2424", "elevation": 36, "timezone": "America/New_York"},
        {"iata": "LGA", "icao": "KLGA", "name": "LaGuardia Airport", "city": "New York", "country": "United States", "latitude": "40.7769", "longitude": "-73.8740", "elevation": 21, "timezone": "America/New_York"},
        {"iata": "BWI", "icao": "KBWI", "name": "Baltimore/Washington International Airport", "city": "Baltimore", "country": "United States", "latitude": "39.1774", "longitude": "-76.6684", "elevation": 146, "timezone": "America/New_York"},
        {"iata": "DCA", "icao": "KDCA", "name": "Ronald Reagan Washington National Airport", "city": "Washington", "country": "United States", "latitude": "38.8512", "longitude": "-77.0402", "elevation": 15, "timezone": "America/New_York"},
        {"iata": "IAD", "icao": "KIAD", "name": "Washington Dulles International Airport", "city": "Washington", "country": "United States", "latitude": "38.9531", "longitude": "-77.4565", "elevation": 313, "timezone": "America/New_York"},
        {"iata": "SAN", "icao": "KSAN", "name": "San Diego International Airport", "city": "San Diego", "country": "United States", "latitude": "32.7336", "longitude": "-117.1897", "elevation": 17, "timezone": "America/Los_Angeles"},
        {"iata": "PDX", "icao": "KPDX", "name": "Portland International Airport", "city": "Portland", "country": "United States", "latitude": "45.5898", "longitude": "-122.5951", "elevation": 31, "timezone": "America/Los_Angeles"},
        {"iata": "YYZ", "icao": "CYYZ", "name": "Toronto Pearson International Airport", "city": "Toronto", "country": "Canada", "latitude": "43.6777", "longitude": "-79.6248", "elevation": 569, "timezone": "America/Toronto"},
        {"iata": "YVR", "icao": "CYVR", "name": "Vancouver International Airport", "city": "Vancouver", "country": "Canada", "latitude": "49.1967", "longitude": "-123.1815", "elevation": 14, "timezone": "America/Vancouver"},
        {"iata": "YUL", "icao": "CYUL", "name": "Montréal-Pierre Elliott Trudeau International Airport", "city": "Montreal", "country": "Canada", "latitude": "45.4657", "longitude": "-73.7413", "elevation": 118, "timezone": "America/Toronto"},
        {"iata": "MEX", "icao": "MMMX", "name": "Mexico City International Airport", "city": "Mexico City", "country": "Mexico", "latitude": "19.4363", "longitude": "-99.0721", "elevation": 7316, "timezone": "America/Mexico_City"},
        
        # Europe
        {"iata": "LHR", "icao": "EGLL", "name": "London Heathrow Airport", "city": "London", "country": "United Kingdom", "latitude": "51.4700", "longitude": "-0.4543", "elevation": 83, "timezone": "Europe/London"},
        {"iata": "CDG", "icao": "LFPG", "name": "Charles de Gaulle Airport", "city": "Paris", "country": "France", "latitude": "49.0097", "longitude": "2.5479", "elevation": 392, "timezone": "Europe/Paris"},
        {"iata": "FRA", "icao": "EDDF", "name": "Frankfurt Airport", "city": "Frankfurt", "country": "Germany", "latitude": "50.0379", "longitude": "8.5622", "elevation": 364, "timezone": "Europe/Berlin"},
        {"iata": "AMS", "icao": "EHAM", "name": "Amsterdam Airport Schiphol", "city": "Amsterdam", "country": "Netherlands", "latitude": "52.3105", "longitude": "4.7683", "elevation": -11, "timezone": "Europe/Amsterdam"},
        {"iata": "MAD", "icao": "LEMD", "name": "Madrid-Barajas Airport", "city": "Madrid", "country": "Spain", "latitude": "40.4839", "longitude": "-3.5680", "elevation": 2169, "timezone": "Europe/Madrid"},
        {"iata": "BCN", "icao": "LEBL", "name": "Barcelona-El Prat Airport", "city": "Barcelona", "country": "Spain", "latitude": "41.2974", "longitude": "2.0833", "elevation": 12, "timezone": "Europe/Madrid"},
        {"iata": "FCO", "icao": "LIRF", "name": "Leonardo da Vinci International Airport", "city": "Rome", "country": "Italy", "latitude": "41.8003", "longitude": "12.2389", "elevation": 13, "timezone": "Europe/Rome"},
        {"iata": "MUC", "icao": "EDDM", "name": "Munich Airport", "city": "Munich", "country": "Germany", "latitude": "48.3537", "longitude": "11.7750", "elevation": 1487, "timezone": "Europe/Berlin"},
        {"iata": "ZUR", "icao": "LSZH", "name": "Zurich Airport", "city": "Zurich", "country": "Switzerland", "latitude": "47.4647", "longitude": "8.5492", "elevation": 1416, "timezone": "Europe/Zurich"},
        {"iata": "VIE", "icao": "LOWW", "name": "Vienna International Airport", "city": "Vienna", "country": "Austria", "latitude": "48.1103", "longitude": "16.5697", "elevation": 600, "timezone": "Europe/Vienna"},
        {"iata": "CPH", "icao": "EKCH", "name": "Copenhagen Airport", "city": "Copenhagen", "country": "Denmark", "latitude": "55.6181", "longitude": "12.6561", "elevation": 17, "timezone": "Europe/Copenhagen"},
        {"iata": "ARN", "icao": "ESSA", "name": "Stockholm Arlanda Airport", "city": "Stockholm", "country": "Sweden", "latitude": "59.6519", "longitude": "17.9186", "elevation": 137, "timezone": "Europe/Stockholm"},
        {"iata": "OSL", "icao": "ENGM", "name": "Oslo Airport", "city": "Oslo", "country": "Norway", "latitude": "60.1939", "longitude": "11.1004", "elevation": 681, "timezone": "Europe/Oslo"},
        {"iata": "HEL", "icao": "EFHK", "name": "Helsinki Airport", "city": "Helsinki", "country": "Finland", "latitude": "60.3172", "longitude": "24.9633", "elevation": 179, "timezone": "Europe/Helsinki"},
        {"iata": "IST", "icao": "LTFM", "name": "Istanbul Airport", "city": "Istanbul", "country": "Turkey", "latitude": "41.2753", "longitude": "28.7519", "elevation": 325, "timezone": "Europe/Istanbul"},
        {"iata": "LIS", "icao": "LPPT", "name": "Lisbon Portela Airport", "city": "Lisbon", "country": "Portugal", "latitude": "38.7742", "longitude": "-9.1342", "elevation": 374, "timezone": "Europe/Lisbon"},
        {"iata": "DUB", "icao": "EIDW", "name": "Dublin Airport", "city": "Dublin", "country": "Ireland", "latitude": "53.4213", "longitude": "-6.2701", "elevation": 242, "timezone": "Europe/Dublin"},
        {"iata": "BRU", "icao": "EBBR", "name": "Brussels Airport", "city": "Brussels", "country": "Belgium", "latitude": "50.9010", "longitude": "4.4856", "elevation": 184, "timezone": "Europe/Brussels"},
        {"iata": "ATH", "icao": "LGAV", "name": "Athens International Airport", "city": "Athens", "country": "Greece", "latitude": "37.9364", "longitude": "23.9445", "elevation": 308, "timezone": "Europe/Athens"},
        
        # Asia
        {"iata": "DXB", "icao": "OMDB", "name": "Dubai International Airport", "city": "Dubai", "country": "United Arab Emirates", "latitude": "25.2532", "longitude": "55.3657", "elevation": 62, "timezone": "Asia/Dubai"},
        {"iata": "SIN", "icao": "WSSS", "name": "Singapore Changi Airport", "city": "Singapore", "country": "Singapore", "latitude": "1.3644", "longitude": "103.9915", "elevation": 22, "timezone": "Asia/Singapore"},
        {"iata": "HKG", "icao": "VHHH", "name": "Hong Kong International Airport", "city": "Hong Kong", "country": "Hong Kong", "latitude": "22.3080", "longitude": "113.9185", "elevation": 28, "timezone": "Asia/Hong_Kong"},
        {"iata": "ICN", "icao": "RKSI", "name": "Incheon International Airport", "city": "Seoul", "country": "South Korea", "latitude": "37.4602", "longitude": "126.4407", "elevation": 23, "timezone": "Asia/Seoul"},
        {"iata": "NRT", "icao": "RJAA", "name": "Narita International Airport", "city": "Tokyo", "country": "Japan", "latitude": "35.7647", "longitude": "140.3864", "elevation": 141, "timezone": "Asia/Tokyo"},
        {"iata": "HND", "icao": "RJTT", "name": "Tokyo Haneda Airport", "city": "Tokyo", "country": "Japan", "latitude": "35.5494", "longitude": "139.7798", "elevation": 35, "timezone": "Asia/Tokyo"},
        {"iata": "PEK", "icao": "ZBAA", "name": "Beijing Capital International Airport", "city": "Beijing", "country": "China", "latitude": "40.0799", "longitude": "116.6031", "elevation": 116, "timezone": "Asia/Shanghai"},
        {"iata": "PVG", "icao": "ZSPD", "name": "Shanghai Pudong International Airport", "city": "Shanghai", "country": "China", "latitude": "31.1443", "longitude": "121.8083", "elevation": 13, "timezone": "Asia/Shanghai"},
        {"iata": "CAN", "icao": "ZGGG", "name": "Guangzhou Baiyun International Airport", "city": "Guangzhou", "country": "China", "latitude": "23.3924", "longitude": "113.2988", "elevation": 50, "timezone": "Asia/Shanghai"},
        {"iata": "DEL", "icao": "VIDP", "name": "Indira Gandhi International Airport", "city": "New Delhi", "country": "India", "latitude": "28.5562", "longitude": "77.1000", "elevation": 777, "timezone": "Asia/Kolkata"},
        {"iata": "BOM", "icao": "VABB", "name": "Chhatrapati Shivaji Maharaj International Airport", "city": "Mumbai", "country": "India", "latitude": "19.0896", "longitude": "72.8656", "elevation": 39, "timezone": "Asia/Kolkata"},
        {"iata": "BKK", "icao": "VTBS", "name": "Suvarnabhumi Airport", "city": "Bangkok", "country": "Thailand", "latitude": "13.6900", "longitude": "100.7501", "elevation": 5, "timezone": "Asia/Bangkok"},
        {"iata": "KUL", "icao": "WMKK", "name": "Kuala Lumpur International Airport", "city": "Kuala Lumpur", "country": "Malaysia", "latitude": "2.7456", "longitude": "101.7072", "elevation": 69, "timezone": "Asia/Kuala_Lumpur"},
        {"iata": "CGK", "icao": "WIII", "name": "Soekarno-Hatta International Airport", "city": "Jakarta", "country": "Indonesia", "latitude": "-6.1256", "longitude": "106.6559", "elevation": 34, "timezone": "Asia/Jakarta"},
        {"iata": "MNL", "icao": "RPLL", "name": "Ninoy Aquino International Airport", "city": "Manila", "country": "Philippines", "latitude": "14.5086", "longitude": "121.0194", "elevation": 75, "timezone": "Asia/Manila"},
        {"iata": "DOH", "icao": "OTHH", "name": "Hamad International Airport", "city": "Doha", "country": "Qatar", "latitude": "25.2731", "longitude": "51.6080", "elevation": 13, "timezone": "Asia/Qatar"},
        {"iata": "AUH", "icao": "OMAA", "name": "Abu Dhabi International Airport", "city": "Abu Dhabi", "country": "United Arab Emirates", "latitude": "24.4330", "longitude": "54.6511", "elevation": 88, "timezone": "Asia/Dubai"},
        {"iata": "SVO", "icao": "UUEE", "name": "Sheremetyevo International Airport", "city": "Moscow", "country": "Russia", "latitude": "55.9728", "longitude": "37.4147", "elevation": 622, "timezone": "Europe/Moscow"},
        
        # South America
        {"iata": "GRU", "icao": "SBGR", "name": "São Paulo-Guarulhos International Airport", "city": "São Paulo", "country": "Brazil", "latitude": "-23.4356", "longitude": "-46.4731", "elevation": 2459, "timezone": "America/Sao_Paulo"},
        {"iata": "GIG", "icao": "SBGL", "name": "Rio de Janeiro-Galeão International Airport", "city": "Rio de Janeiro", "country": "Brazil", "latitude": "-22.8099", "longitude": "-43.2505", "elevation": 28, "timezone": "America/Sao_Paulo"},
        {"iata": "BOG", "icao": "SKBO", "name": "El Dorado International Airport", "city": "Bogotá", "country": "Colombia", "latitude": "4.7016", "longitude": "-74.1469", "elevation": 8361, "timezone": "America/Bogota"},
        {"iata": "LIM", "icao": "SPJC", "name": "Jorge Chávez International Airport", "city": "Lima", "country": "Peru", "latitude": "-12.0219", "longitude": "-77.1143", "elevation": 113, "timezone": "America/Lima"},
        {"iata": "EZE", "icao": "SAEZ", "name": "Ezeiza International Airport", "city": "Buenos Aires", "country": "Argentina", "latitude": "-34.8222", "longitude": "-58.5358", "elevation": 67, "timezone": "America/Argentina/Buenos_Aires"},
        {"iata": "SCL", "icao": "SCEL", "name": "Santiago International Airport", "city": "Santiago", "country": "Chile", "latitude": "-33.3928", "longitude": "-70.7856", "elevation": 1555, "timezone": "America/Santiago"},
        
        # Oceania
        {"iata": "SYD", "icao": "YSSY", "name": "Sydney Kingsford Smith Airport", "city": "Sydney", "country": "Australia", "latitude": "-33.9399", "longitude": "151.1753", "elevation": 21, "timezone": "Australia/Sydney"},
        {"iata": "MEL", "icao": "YMML", "name": "Melbourne Airport", "city": "Melbourne", "country": "Australia", "latitude": "-37.6733", "longitude": "144.8433", "elevation": 434, "timezone": "Australia/Melbourne"},
        {"iata": "BNE", "icao": "YBBN", "name": "Brisbane Airport", "city": "Brisbane", "country": "Australia", "latitude": "-27.3942", "longitude": "153.1218", "elevation": 13, "timezone": "Australia/Brisbane"},
        {"iata": "PER", "icao": "YPPH", "name": "Perth Airport", "city": "Perth", "country": "Australia", "latitude": "-31.9403", "longitude": "115.9669", "elevation": 67, "timezone": "Australia/Perth"},
        {"iata": "AKL", "icao": "NZAA", "name": "Auckland Airport", "city": "Auckland", "country": "New Zealand", "latitude": "-37.0082", "longitude": "174.7850", "elevation": 23, "timezone": "Pacific/Auckland"},
        
        # Africa
        {"iata": "JNB", "icao": "FAJS", "name": "O.R. Tambo International Airport", "city": "Johannesburg", "country": "South Africa", "latitude": "-26.1392", "longitude": "28.2460", "elevation": 5558, "timezone": "Africa/Johannesburg"},
        {"iata": "CPT", "icao": "FACT", "name": "Cape Town International Airport", "city": "Cape Town", "country": "South Africa", "latitude": "-33.9648", "longitude": "18.6017", "elevation": 151, "timezone": "Africa/Johannesburg"},
        {"iata": "CAI", "icao": "HECA", "name": "Cairo International Airport", "city": "Cairo", "country": "Egypt", "latitude": "30.1219", "longitude": "31.4056", "elevation": 382, "timezone": "Africa/Cairo"},
        {"iata": "ADD", "icao": "HAAB", "name": "Addis Ababa Bole International Airport", "city": "Addis Ababa", "country": "Ethiopia", "latitude": "8.9779", "longitude": "38.7992", "elevation": 7625, "timezone": "Africa/Addis_Ababa"},
        {"iata": "NBO", "icao": "HKJK", "name": "Jomo Kenyatta International Airport", "city": "Nairobi", "country": "Kenya", "latitude": "-1.3192", "longitude": "36.9278", "elevation": 5327, "timezone": "Africa/Nairobi"},
        {"iata": "LOS", "icao": "DNMM", "name": "Murtala Muhammed International Airport", "city": "Lagos", "country": "Nigeria", "latitude": "6.5774", "longitude": "3.3212", "elevation": 135, "timezone": "Africa/Lagos"},
        
        # Additional Major Airports
        {"iata": "TPE", "icao": "RCTP", "name": "Taiwan Taoyuan International Airport", "city": "Taipei", "country": "Taiwan", "latitude": "25.0797", "longitude": "121.2342", "elevation": 106, "timezone": "Asia/Taipei"},
        {"iata": "KIX", "icao": "RJBB", "name": "Kansai International Airport", "city": "Osaka", "country": "Japan", "latitude": "34.4347", "longitude": "135.2440", "elevation": 26, "timezone": "Asia/Tokyo"},
        {"iata": "BLR", "icao": "VOBL", "name": "Kempegowda International Airport", "city": "Bangalore", "country": "India", "latitude": "13.1979", "longitude": "77.7063", "elevation": 3000, "timezone": "Asia/Kolkata"},
        {"iata": "HYD", "icao": "VOHS", "name": "Rajiv Gandhi International Airport", "city": "Hyderabad", "country": "India", "latitude": "17.2403", "longitude": "78.4294", "elevation": 2024, "timezone": "Asia/Kolkata"},
        {"iata": "CMB", "icao": "VCBI", "name": "Bandaranaike International Airport", "city": "Colombo", "country": "Sri Lanka", "latitude": "7.1808", "longitude": "79.8841", "elevation": 30, "timezone": "Asia/Colombo"},
        {"iata": "DAC", "icao": "VGHS", "name": "Hazrat Shahjalal International Airport", "city": "Dhaka", "country": "Bangladesh", "latitude": "23.8433", "longitude": "90.3978", "elevation": 30, "timezone": "Asia/Dhaka"},
        {"iata": "KTM", "icao": "VNKT", "name": "Tribhuvan International Airport", "city": "Kathmandu", "country": "Nepal", "latitude": "27.6966", "longitude": "85.3591", "elevation": 4390, "timezone": "Asia/Kathmandu"},
        {"iata": "RGN", "icao": "VYYY", "name": "Yangon International Airport", "city": "Yangon", "country": "Myanmar", "latitude": "16.9073", "longitude": "96.1332", "elevation": 109, "timezone": "Asia/Yangon"},
        {"iata": "HAN", "icao": "VVNB", "name": "Noi Bai International Airport", "city": "Hanoi", "country": "Vietnam", "latitude": "21.2212", "longitude": "105.8072", "elevation": 39, "timezone": "Asia/Ho_Chi_Minh"},
        {"iata": "SGN", "icao": "VVTS", "name": "Tan Son Nhat International Airport", "city": "Ho Chi Minh City", "country": "Vietnam", "latitude": "10.8188", "longitude": "106.6519", "elevation": 33, "timezone": "Asia/Ho_Chi_Minh"},
        {"iata": "CEB", "icao": "RPVM", "name": "Mactan-Cebu International Airport", "city": "Cebu", "country": "Philippines", "latitude": "10.3075", "longitude": "123.9790", "elevation": 31, "timezone": "Asia/Manila"},
        {"iata": "DPS", "icao": "WADD", "name": "Ngurah Rai International Airport", "city": "Denpasar", "country": "Indonesia", "latitude": "-8.7482", "longitude": "115.1670", "elevation": 14, "timezone": "Asia/Makassar"},
        {"iata": "SUB", "icao": "WARR", "name": "Juanda International Airport", "city": "Surabaya", "country": "Indonesia", "latitude": "-7.3798", "longitude": "112.7869", "elevation": 9, "timezone": "Asia/Jakarta"},
        {"iata": "CTS", "icao": "RJCC", "name": "New Chitose Airport", "city": "Sapporo", "country": "Japan", "latitude": "42.7752", "longitude": "141.6920", "elevation": 82, "timezone": "Asia/Tokyo"},
        {"iata": "FUK", "icao": "RJFF", "name": "Fukuoka Airport", "city": "Fukuoka", "country": "Japan", "latitude": "33.5859", "longitude": "130.4511", "elevation": 32, "timezone": "Asia/Tokyo"},
        {"iata": "XIY", "icao": "ZLXY", "name": "Xi'an Xianyang International Airport", "city": "Xi'an", "country": "China", "latitude": "34.4471", "longitude": "108.7514", "elevation": 1572, "timezone": "Asia/Shanghai"},
        {"iata": "CTU", "icao": "ZUUU", "name": "Chengdu Shuangliu International Airport", "city": "Chengdu", "country": "China", "latitude": "30.5785", "longitude": "103.9470", "elevation": 1625, "timezone": "Asia/Shanghai"},
        {"iata": "SZX", "icao": "ZGSZ", "name": "Shenzhen Bao'an International Airport", "city": "Shenzhen", "country": "China", "latitude": "22.6393", "longitude": "113.8108", "elevation": 13, "timezone": "Asia/Shanghai"},
        {"iata": "CKG", "icao": "ZUCK", "name": "Chongqing Jiangbei International Airport", "city": "Chongqing", "country": "China", "latitude": "29.7192", "longitude": "106.6417", "elevation": 1365, "timezone": "Asia/Shanghai"},
        {"iata": "WUH", "icao": "ZHHH", "name": "Wuhan Tianhe International Airport", "city": "Wuhan", "country": "China", "latitude": "30.7838", "longitude": "114.2081", "elevation": 113, "timezone": "Asia/Shanghai"},
    ]
    
    # Add key field for each airport
    for airport in airports:
        airport['key'] = f"airport_{airport['iata'].lower()}"
        airport['id'] = airport['iata']
    
    return airports

if __name__ == '__main__':
    airports = generate_airports()
    print(f"Generated {len(airports)} airports")
    for i, airport in enumerate(airports[:5], 1):
        print(f"{i}. {airport['name']} ({airport['iata']}) - {airport['city']}, {airport['country']}")
