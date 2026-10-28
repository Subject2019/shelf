package com.echoshelf.app.data

import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.PUT
import retrofit2.http.Path
import retrofit2.http.Query

interface EchoShelfApi {
    @POST("auth/login")
    suspend fun login(@Body body: LoginRequest): TokenResponse

    @POST("auth/refresh")
    suspend fun refresh(@Body body: RefreshRequest): TokenResponse

    @POST("auth/logout")
    suspend fun logout(@Body body: RefreshRequest)

    @GET("books")
    suspend fun books(
        @Query("page") page: Int = 1,
        @Query("page_size") pageSize: Int = 100,
    ): BookList

    @GET("books/{id}")
    suspend fun book(@Path("id") id: Int): BookDetail

    @PUT("progress/{id}")
    suspend fun putProgress(@Path("id") id: Int, @Body body: ProgressPut): ProgressResult
}
