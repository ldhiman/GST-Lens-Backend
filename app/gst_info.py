import requests

state_code_map = {
    "01": "Jammu & Kashmir",
    "02": "Himachal Pradesh",
    "03": "Punjab",
    "04": "Chandigarh",
    "05": "Uttarakhand",
    "06": "Haryana",
    "07": "Delhi",
    "08": "Rajasthan",
    "09": "Uttar Pradesh",
    "10": "Bihar",
    "11": "Sikkim",
    "12": "Arunachal Pradesh",
    "13": "Nagaland",
    "14": "Manipur",
    "15": "Mizoram",
    "16": "Tripura",
    "17": "Meghalaya",
    "18": "Assam",
    "19": "West Bengal",
    "20": "Jharkhand",
    "21": "Odisha",
    "22": "Chhattisgarh",
    "23": "Madhya Pradesh",
    "24": "Gujarat",
    "26": "Dadra and Nagar Haveli and Daman and Diu",
    "27": "Maharashtra",
    "28": "Andhra Pradesh (Old)",
    "29": "Karnataka",
    "30": "Goa",
    "31": "Lakshadweep",
    "32": "Kerala",
    "33": "Tamil Nadu",
    "34": "Puducherry",
    "35": "Andaman & Nicobar Islands",
    "36": "Telangana",
    "37": "Andhra Pradesh (New)",
    "38": "Ladakh",
    "97": "Other Territory",
    "99": "Centre Jurisdiction"
}


def get_state_name(code):
    str_code = str(code).zfill(2)
    return state_code_map.get(str_code, "Invalid Code")


def get_gst_info_1(gstin: str):
    url = f"https://blog-backend.mastersindia.co/api/v1/custom/search/gstin/?keyword={gstin}&unique_id=7jfRGwv8SVkxCTvYXLwyHO4HUYiQRL"
    headers = {
        'accept': 'application/json, text/plain, */*',
        'accept-language': 'en-US,en;q=0.9,hi;q=0.8',
        'cache-control': 'no-cache',
        'dnt': '1',
        'origin': 'https://www.mastersindia.co',
        'pragma': 'no-cache',
        'referer': 'https://www.mastersindia.co/gst-number-search-and-gstin-verification/',
        'sec-ch-ua': '"Google Chrome";v="143", "Chromium";v="143", "Not A(Brand";v="24"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"',
        'sec-fetch-dest': 'empty',
        'sec-fetch-mode': 'cors',
        'sec-fetch-site': 'same-site',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36'
    }
    try:
        response = requests.get(url, headers=headers, timeout=5)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        print(f"Error fetching GST source 1: {e}")
    return {}


def get_gst_info_2(gstin: str):
    url = "https://api.cashfree.com/verification/marketing/gstin"
    headers = {
        'accept': 'application/json, text/plain, */*',
        'accept-language': 'en-US,en;q=0.9,hi;q=0.8',
        'cache-control': 'no-cache',
        'content-type': 'application/json',
        'origin': 'https://www.cashfree.com',
        'dnt': '1',
        'pragma': 'no-cache',
        'referer': 'https://www.cashfree.com/',
        'sec-ch-ua': '"Google Chrome";v="146", "Chromium";v="146", "Not A(Brand";v="24"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"',
        'sec-fetch-dest': 'empty',
        'sec-fetch-mode': 'cors',
        'sec-fetch-site': 'same-site',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36',
    }
    data = {"GSTIN": gstin}
    try:
        response = requests.post(url, headers=headers, json=data, timeout=5)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        print(f"Error fetching GST source 2: {e}")
    return {}


def get_gst_info(gstin: str):
    gstin = gstin.strip().upper()
    data1 = get_gst_info_1(gstin)
    data2 = get_gst_info_2(gstin)

    s1_data = data1.get("data", {}) if isinstance(data1, dict) else {}
    if not isinstance(data2, dict):
        data2 = {}

    legal_name = (
        data2.get("legal_business_name")
        or s1_data.get("lgnm")
        or data2.get("trade_name_of_business")
    )
    trade_name = (
        data2.get("trade_name")
        or s1_data.get("tradeNam")
        or data2.get("legal_name_of_business")
    )
    has_valid_name = bool(legal_name or trade_name)
    raw_status = (
        data2.get("gstin_uin_status")
        or s1_data.get("sts")
        or data2.get("gstin_in_status")
    )
    status = raw_status if raw_status else ("Active" if has_valid_name else "Inactive / Not Found")
    constitution = s1_data.get("ctb") or data2.get("constitution_of_business")

    return {
        "gstin": gstin,
        "legal_name": legal_name or "N/A",
        "trade_name": trade_name or legal_name or "N/A",
        "status": status,
        "constitution": constitution or "N/A",
        "state_code": gstin[:2],
        "state": get_state_name(gstin[:2]),
        "pan_number": gstin[2:12],
    }


if __name__ == "__main__":
    gstin = "07BLNPR7449R1ZT"
    gst_info = get_gst_info(gstin)
    print(gst_info)
