const phAddressData = {
    "Misamis Oriental": {
        "Cagayan de Oro": {
            "zip": "9000",
            "barangays": ["Carmen", "Balulang", "Nazareth", "Lapasan", "Kauswagan", "Macabalan", "Patag", "Bulua", "Camaman-an", "Indahag", "Lumbia"]
        },
        "Gingoog": {
            "zip": "9014",
            "barangays": ["Agay-ayan", "Anakan", "Lunao", "Magsaysay", "Poblacion", "San Juan"]
        },
        "El Salvador": {
            "zip": "9017",
            "barangays": ["Amoros", "Bolisong", "Cogon", "Poblacion"]
        }
    },
    "Surigao Del Norte": {
        "Gigaquit": {
            "zip": "8409",
            "barangays": ["Sico-sico", "Alambique", "Anibongan", "Camam-onan", "Villahermosa", "San Isidro", "Mahanub"]
        },
        "Surigao City": {
            "zip": "8400",
            "barangays": ["Taft", "Washington", "San Juan", "Luna", "Canlanipa", "Cagniog"]
        },
        "Mainit": {
            "zip": "8407",
            "barangays": ["Magsaysay", "Matin-ao", "Paco"]
        }
    },
    "Metro Manila": {
        "Manila": {
            "zip": "1000",
            "barangays": ["Binondo", "Ermita", "Intramuros", "Malate", "Paco", "Pandacan", "Quiapo", "Sampaloc"]
        },
        "Quezon City": {
            "zip": "1100",
            "barangays": ["Diliman", "Cubao", "Batasan Hills", "Commonwealth", "Loyola Heights"]
        },
        "Makati": {
            "zip": "1200",
            "barangays": ["Bel-Air", "Forbes Park", "Poblacion", "San Lorenzo", "Urdaneta"]
        }
    },
    "Cebu": {
        "Cebu City": {
            "zip": "6000",
            "barangays": ["Lahug", "Mabolo", "Pardo", "Tisa", "Guadalupe"]
        },
        "Mandaue City": {
            "zip": "6014",
            "barangays": ["Bakilid", "Banilad", "Centro", "Subangdaku"]
        },
        "Lapu-Lapu City": {
            "zip": "6015",
            "barangays": ["Basak", "Maribago", "Pajac", "Pajo"]
        }
    },
    "Davao Del Sur": {
        "Davao City": {
            "zip": "8000",
            "barangays": ["Buhangin", "Matina", "Toril", "Agdao", "Talomo"]
        }
    }
};

function initAddressSelectors(cityId, munId, brgyId, zipId) {
    const cityInput = document.getElementById(cityId);
    const munInput = document.getElementById(munId);
    const brgyInput = document.getElementById(brgyId);
    const zipInput = document.getElementById(zipId);

    const munList = document.getElementById(munId + 'List');
    const brgyList = document.getElementById(brgyId + 'List');

    cityInput.addEventListener('input', () => {
        const province = cityInput.value.trim();
        const provKey = province.toLowerCase();

        munList.innerHTML = '';
        brgyList.innerHTML = '';
        munInput.value = '';
        brgyInput.value = '';
        zipInput.value = '';

        const matchedProv = Object.keys(phAddressData).find(k => k.toLowerCase() === provKey);
        if (matchedProv) {
            Object.keys(phAddressData[matchedProv]).forEach(mun => {
                const opt = document.createElement('option');
                opt.value = mun;
                munList.appendChild(opt);
            });
        }
    });

    munInput.addEventListener('input', () => {
        const province = cityInput.value.trim();
        const provKey = province.toLowerCase();
        const municipality = munInput.value.trim();
        const munKey = municipality.toLowerCase();

        brgyList.innerHTML = '';
        brgyInput.value = '';
        zipInput.value = '';

        const matchedProv = Object.keys(phAddressData).find(k => k.toLowerCase() === provKey);
        if (matchedProv) {
            const matchedMun = Object.keys(phAddressData[matchedProv]).find(k => k.toLowerCase() === munKey);
            if (matchedMun) {
                const data = phAddressData[matchedProv][matchedMun];
                zipInput.value = data.zip;
                data.barangays.forEach(brgy => {
                    const opt = document.createElement('option');
                    opt.value = brgy;
                    brgyList.appendChild(opt);
                });
            }
        }
    });
}
