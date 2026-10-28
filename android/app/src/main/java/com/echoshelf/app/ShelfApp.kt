package com.echoshelf.app

import android.app.Application

class ShelfApp : Application() {
    lateinit var graph: AppGraph
        private set

    override fun onCreate() {
        super.onCreate()
        instance = this
        graph = AppGraph(this)
    }

    companion object {
        lateinit var instance: ShelfApp
            private set
    }
}
