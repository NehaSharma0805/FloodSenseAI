document.addEventListener("DOMContentLoaded", function () {

    const button = document.querySelector(".predict-btn");

    button.addEventListener("click", function () {

        const lat = document.getElementById("lat").value;
        const lon = document.getElementById("lon").value;
        const locationInput = document.getElementById("location-name");
        const locationName = locationInput.value.trim();
        alert(locationName);
        console.log("Location Name:", locationName);
        if (!lat || !lon) {
            alert("Please select coordinates first.");
            return;
        }

        console.log("Sending data to backend...");
        
        document.getElementById("loading-overlay").style.display = "flex";
        console.log(locationName);
        fetch("/analyze", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                latitude: lat,
                longitude: lon,
                location_name: locationName
            })
        })
        .then(response => response.json())
        .then(data => {
         // store result temporarily
         localStorage.setItem("prediction", JSON.stringify(data));
          // move to result page
          window.location.href = "/result";
         })

        .catch(error => {
            console.error("Fetch error:", error);
            document.getElementById("loading-overlay").style.display = "none";
        });

    });

});
