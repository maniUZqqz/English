from django.shortcuts import render



def homeTeach(request):

    return render(
        request,
        "PDF/input.html",
        # {"form": form}
    )
